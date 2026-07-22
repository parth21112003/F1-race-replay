"""
Race Event Detector — Rule-based engine for detecting race events from telemetry frames.

Detects:
  - Overtakes (with DRS-assisted flag)
  - Pit stops (with tyre compound change + duration)
  - Fastest laps
  - Safety car / VSC deployments (with field spread analysis)

Each detected event is a dict:
  {
      "type":       "overtake" | "pit_stop" | "fastest_lap" | "safety_car",
      "time":       float,      # session time in seconds
      "lap":        int,
      "driver":     str,        # primary driver code
      "commentary": str,        # human-readable sentence
      "details":    dict,       # type-specific extras
      "priority":   int,        # 1=critical, 2=important, 3=normal
  }
"""

from __future__ import annotations

from src.lib.tyres import TYRE_COMPOUND_NAMES


# ── helpers ──────────────────────────────────────────────────────────────
def _fmt_time(seconds: float) -> str:
    """Format seconds into M:SS.mmm lap-time string."""
    mins = int(seconds // 60)
    secs = seconds % 60
    return f"{mins}:{secs:06.3f}"


def _tyre_name(tyre_int: float | int) -> str:
    """Map numeric tyre compound id to human name."""
    try:
        return TYRE_COMPOUND_NAMES.get(int(tyre_int), "UNKNOWN")
    except (ValueError, TypeError):
        return "UNKNOWN"


# ── main detector ────────────────────────────────────────────────────────

class RaceEventDetector:
    """Analyse a completed list of frames and return detected race events."""

    def __init__(self, frames: list[dict], track_statuses: list[dict],
                 total_laps: int = 0):
        self.frames = frames
        self.track_statuses = track_statuses
        self.total_laps = total_laps

    # ── public API ───────────────────────────────────────────────────────

    def detect_all(self) -> list[dict]:
        """Run every detection pass and return a merged, sorted event list."""
        events: list[dict] = []
        events.extend(self._detect_overtakes())
        events.extend(self._detect_pit_stops())
        events.extend(self._detect_fastest_laps())
        events.extend(self._detect_safety_car())
        events.sort(key=lambda e: e["time"])
        return events

    # ── overtake detection ───────────────────────────────────────────────

    def _detect_overtakes(self) -> list[dict]:
        events: list[dict] = []
        if len(self.frames) < 2:
            return events

        # Debounce: after detecting a swap, confirm new positions persist for N frames
        DEBOUNCE_FRAMES = 5
        # Skip early-race chaos (first 2 laps)
        MIN_LAP = 3
        # DRS look-back: if overtaker had DRS active within this many frames
        DRS_LOOKBACK = 75  # ~3 seconds at 25 FPS
        # Cooldown per driver pair to avoid duplicate events
        COOLDOWN_FRAMES = 50

        # Track pending swaps for debouncing:
        #   key=(overtaker, overtaken) -> {frame_detected, overtaker_pos, overtaken_pos, count, lap}
        pending: dict[tuple[str, str], dict] = {}
        # Cooldown tracker: key -> last frame an event was emitted
        cooldown: dict[tuple[str, str], int] = {}

        prev_positions: dict[str, int] = {}

        for fi, frame in enumerate(self.frames):
            drivers = frame.get("drivers", {})
            cur_positions: dict[str, int] = {}
            cur_laps: dict[str, int] = {}

            for code, info in drivers.items():
                cur_positions[code] = info.get("position", 99)
                cur_laps[code] = info.get("lap", 1)

            if prev_positions:
                # Detect NEW swaps (initial detection)
                for code_a in cur_positions:
                    for code_b in cur_positions:
                        if code_a >= code_b:
                            continue
                        pos_a_prev = prev_positions.get(code_a, 99)
                        pos_b_prev = prev_positions.get(code_b, 99)
                        pos_a_now = cur_positions[code_a]
                        pos_b_now = cur_positions[code_b]

                        # Determine if a swap occurred this frame
                        if pos_a_prev > pos_b_prev and pos_a_now < pos_b_now:
                            overtaker, overtaken = code_a, code_b
                        elif pos_b_prev > pos_a_prev and pos_b_now < pos_a_now:
                            overtaker, overtaken = code_b, code_a
                        else:
                            continue

                        key = (overtaker, overtaken)
                        # Skip if on cooldown
                        if key in cooldown and fi - cooldown[key] < COOLDOWN_FRAMES:
                            continue
                        # Skip if already pending
                        if key in pending:
                            continue
                        # Skip pit-related swaps
                        if drivers.get(overtaker, {}).get("in_pit", False):
                            continue
                        if drivers.get(overtaken, {}).get("in_pit", False):
                            continue
                        # Skip early laps
                        lap = cur_laps.get(overtaker, 1)
                        if lap < MIN_LAP:
                            continue

                        pending[key] = {
                            "frame_detected": fi,
                            "overtaker_pos": cur_positions[overtaker],
                            "count": 1,
                            "lap": lap,
                        }

                # Update pending confirmations: check that positions persist
                expired = []
                for key, state in pending.items():
                    overtaker, overtaken = key
                    ot_pos = cur_positions.get(overtaker, 99)
                    od_pos = cur_positions.get(overtaken, 99)

                    if ot_pos < od_pos:
                        # Swap still holds
                        state["count"] += 1
                        if state["count"] >= DEBOUNCE_FRAMES:
                            # Confirmed overtake! Check DRS
                            drs_assisted = False
                            lookback_start = max(0, fi - DRS_LOOKBACK)
                            for li in range(lookback_start, fi + 1):
                                lf = self.frames[li]
                                ld = lf.get("drivers", {}).get(overtaker, {})
                                if ld.get("drs", 0) >= 10:
                                    drs_assisted = True
                                    break

                            t = frame["t"]
                            lap = state["lap"]
                            drs_tag = " using DRS" if drs_assisted else ""
                            commentary = (
                                f"{overtaker} overtakes {overtaken} on Lap {lap}{drs_tag}"
                            )
                            events.append({
                                "type": "overtake",
                                "time": t,
                                "lap": lap,
                                "driver": overtaker,
                                "commentary": commentary,
                                "details": {
                                    "overtaken": overtaken,
                                    "drs_assisted": drs_assisted,
                                    "new_position": ot_pos,
                                },
                                "priority": 3,
                            })
                            cooldown[key] = fi
                            expired.append(key)
                    else:
                        # Swap reverted — false positive
                        expired.append(key)

                for key in expired:
                    pending.pop(key, None)

            prev_positions = cur_positions

        return events

    # ── pit stop detection ───────────────────────────────────────────────

    def _detect_pit_stops(self) -> list[dict]:
        events: list[dict] = []
        if not self.frames:
            return events

        # Track per-driver pit state
        driver_pit_state: dict[str, dict] = {}

        for fi, frame in enumerate(self.frames):
            drivers = frame.get("drivers", {})
            t = frame["t"]

            for code, info in drivers.items():
                in_pit = info.get("in_pit", False)
                state = driver_pit_state.get(code)

                if state is None:
                    driver_pit_state[code] = {
                        "was_in_pit": in_pit,
                        "entry_time": None,
                        "entry_tyre": info.get("tyre"),
                        "entry_lap": info.get("lap", 1),
                    }
                    continue

                # Transition: not in pit → in pit  (pit entry)
                if not state["was_in_pit"] and in_pit:
                    state["entry_time"] = t
                    state["entry_tyre"] = info.get("tyre")
                    state["entry_lap"] = info.get("lap", 1)

                # Transition: in pit → not in pit  (pit exit)
                elif state["was_in_pit"] and not in_pit:
                    entry_time = state.get("entry_time")
                    if entry_time is not None:
                        duration = t - entry_time
                        old_tyre = _tyre_name(state.get("entry_tyre"))
                        new_tyre = _tyre_name(info.get("tyre"))
                        lap = state.get("entry_lap", info.get("lap", 1))

                        tyre_change = ""
                        if old_tyre != new_tyre:
                            tyre_change = f" — {old_tyre} → {new_tyre}"

                        commentary = (
                            f"{code} pits on Lap {lap}{tyre_change} ({duration:.1f}s)"
                        )
                        events.append({
                            "type": "pit_stop",
                            "time": entry_time,
                            "lap": lap,
                            "driver": code,
                            "commentary": commentary,
                            "details": {
                                "duration": round(duration, 1),
                                "old_tyre": old_tyre,
                                "new_tyre": new_tyre,
                            },
                            "priority": 2,
                        })
                    state["entry_time"] = None

                state["was_in_pit"] = in_pit

        return events

    # ── fastest lap detection ────────────────────────────────────────────

    def _detect_fastest_laps(self) -> list[dict]:
        events: list[dict] = []
        if not self.frames:
            return events

        # Track per-driver lap start times
        driver_lap_start: dict[str, dict] = {}  # code -> {lap, start_time}
        overall_fastest: float | None = None
        overall_fastest_driver: str = ""

        for fi, frame in enumerate(self.frames):
            drivers = frame.get("drivers", {})
            t = frame["t"]

            for code, info in drivers.items():
                lap = info.get("lap", 1)
                state = driver_lap_start.get(code)

                if state is None:
                    driver_lap_start[code] = {"lap": lap, "start_time": t}
                    continue

                # Lap boundary crossed
                if lap > state["lap"]:
                    lap_time = t - state["start_time"]

                    # Sanity: lap times should be between 50s and 180s
                    if 50.0 < lap_time < 180.0:
                        if overall_fastest is None or lap_time < overall_fastest:
                            overall_fastest = lap_time
                            overall_fastest_driver = code
                            commentary = (
                                f"{code} sets FASTEST LAP — "
                                f"{_fmt_time(lap_time)} on Lap {state['lap']}"
                            )
                            events.append({
                                "type": "fastest_lap",
                                "time": t,
                                "lap": state["lap"],
                                "driver": code,
                                "commentary": commentary,
                                "details": {
                                    "lap_time": round(lap_time, 3),
                                    "lap_time_str": _fmt_time(lap_time),
                                },
                                "priority": 2,
                            })

                    state["lap"] = lap
                    state["start_time"] = t

        return events

    # ── safety car detection ─────────────────────────────────────────────

    def _detect_safety_car(self) -> list[dict]:
        events: list[dict] = []
        if not self.track_statuses:
            return events

        for status in self.track_statuses:
            status_code = str(status.get("status", ""))
            start_time = status.get("start_time", 0)

            # Find the lap at this time from the closest frame
            lap = self._lap_at_time(start_time)

            if status_code == "4":
                commentary = f"SAFETY CAR DEPLOYED on Lap {lap}"
                events.append({
                    "type": "safety_car",
                    "time": start_time,
                    "lap": lap,
                    "driver": "SC",
                    "commentary": commentary,
                    "details": {"sub_type": "SC"},
                    "priority": 1,
                })
            elif status_code in ("6", "7"):
                commentary = f"VIRTUAL SAFETY CAR on Lap {lap}"
                events.append({
                    "type": "safety_car",
                    "time": start_time,
                    "lap": lap,
                    "driver": "VSC",
                    "commentary": commentary,
                    "details": {"sub_type": "VSC"},
                    "priority": 1,
                })
            elif status_code == "5":
                commentary = f"RED FLAG on Lap {lap}"
                events.append({
                    "type": "safety_car",
                    "time": start_time,
                    "lap": lap,
                    "driver": "RED",
                    "commentary": commentary,
                    "details": {"sub_type": "RED_FLAG"},
                    "priority": 1,
                })

        return events

    # ── helpers ───────────────────────────────────────────────────────────

    def _lap_at_time(self, t: float) -> int:
        """Return the leader lap at the given session time."""
        if not self.frames:
            return 1
        # Binary search for closest frame
        lo, hi = 0, len(self.frames) - 1
        while lo < hi:
            mid = (lo + hi) // 2
            if self.frames[mid]["t"] < t:
                lo = mid + 1
            else:
                hi = mid
        frame = self.frames[lo]
        return frame.get("lap", 1)
