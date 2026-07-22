"""
AI Commentary Engine — Uses Google Gemini to generate broadcast-quality
race commentary from raw event data + telemetry context.

Each detected event (overtake, pit stop, fastest lap, safety car) is enriched
with a natural-language commentary that considers tyre strategy, race context,
and the drama of the situation.

Falls back gracefully to template commentary when:
  - No API key is configured
  - The API call fails
  - AI commentary is disabled in settings
"""

from __future__ import annotations

import time
from typing import Optional

from src.lib.settings import get_settings


# ── helpers ──────────────────────────────────────────────────────────────

def _fmt_time(seconds: float) -> str:
    """Format seconds into M:SS.mmm lap-time string."""
    mins = int(seconds // 60)
    secs = seconds % 60
    return f"{mins}:{secs:06.3f}"


def _fmt_race_time(seconds: float) -> str:
    """Format session seconds as H:MM:SS."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h}:{m:02}:{s:02}"


SYSTEM_PROMPT = """\
You are an expert Formula 1 race commentator providing live broadcast commentary.

Rules:
- Write 2–3 sentences MAX. Be concise but dramatic.
- Use the driver's surname (e.g., "Verstappen", "Hamilton"), not their 3-letter code.
- Reference specific data: lap numbers, tyre compounds, pit stop durations, DRS usage.
- Add strategic insight when possible (e.g., "this undercut could prove decisive").
- Match the event's intensity: safety cars are dramatic, routine pit stops are calm.
- Never fabricate data. Only reference information provided in the context.
- Do NOT use markdown formatting. Write plain text only.

Driver code to name mapping (use surnames only):
VER=Verstappen, HAM=Hamilton, NOR=Norris, LEC=Leclerc, SAI=Sainz,
PIA=Piastri, RUS=Russell, PER=Perez, ALO=Alonso, STR=Stroll,
GAS=Gasly, OCO=Ocon, HUL=Hulkenberg, MAG=Magnussen, TSU=Tsunoda,
RIC=Ricciardo, ALB=Albon, SAR=Sargeant, BOT=Bottas, ZHO=Zhou,
LAW=Lawson, COL=Colapinto, BEA=Bearman, DOO=Doohan, ANT=Antonelli,
HAD=Hadjar, BOR=Bortoleto
"""


# ── Driver code → surname fallback map ───────────────────────────────────

DRIVER_NAMES = {
    "VER": "Verstappen", "HAM": "Hamilton", "NOR": "Norris",
    "LEC": "Leclerc", "SAI": "Sainz", "PIA": "Piastri",
    "RUS": "Russell", "PER": "Perez", "ALO": "Alonso",
    "STR": "Stroll", "GAS": "Gasly", "OCO": "Ocon",
    "HUL": "Hulkenberg", "MAG": "Magnussen", "TSU": "Tsunoda",
    "RIC": "Ricciardo", "ALB": "Albon", "SAR": "Sargeant",
    "BOT": "Bottas", "ZHO": "Zhou", "LAW": "Lawson",
    "COL": "Colapinto", "BEA": "Bearman", "DOO": "Doohan",
    "ANT": "Antonelli", "HAD": "Hadjar", "BOR": "Bortoleto",
}


def _driver_name(code: str) -> str:
    """Get driver surname from 3-letter code, fallback to code itself."""
    return DRIVER_NAMES.get(code, code)


# ── Context extraction ───────────────────────────────────────────────────

def extract_event_context(event: dict, frames: list[dict],
                          all_events: list[dict]) -> dict:
    """
    Build a rich context dict around an event for the LLM prompt.

    Includes:
      - Current top-10 standings at event time
      - Tyre compounds + life for involved drivers
      - Weather conditions
      - Recent events (last 3 before this one)
    """
    event_time = event.get("time", 0)
    event_type = event.get("type", "")
    driver = event.get("driver", "")

    # Find the closest frame to the event time
    closest_frame = None
    best_dt = float("inf")
    for frame in frames:
        dt = abs(frame["t"] - event_time)
        if dt < best_dt:
            best_dt = dt
            closest_frame = frame
        # Early exit: frames are sorted by time, once we pass the event
        # and start getting further away, stop looking
        if frame["t"] > event_time and dt > best_dt:
            break

    context: dict = {
        "event_type": event_type,
        "event_time": _fmt_race_time(event_time),
        "event_lap": event.get("lap", "?"),
        "driver": driver,
        "driver_name": _driver_name(driver),
        "commentary_template": event.get("commentary", ""),
        "details": event.get("details", {}),
    }

    if closest_frame:
        drivers = closest_frame.get("drivers", {})

        # Top-10 standings
        sorted_drivers = sorted(
            drivers.items(),
            key=lambda kv: kv[1].get("position", 99)
        )
        standings = []
        for code, info in sorted_drivers[:10]:
            standings.append({
                "pos": info.get("position", "?"),
                "driver": _driver_name(code),
                "code": code,
                "lap": info.get("lap", "?"),
                "tyre": _tyre_name_from_int(info.get("tyre", 0)),
                "tyre_life": int(info.get("tyre_life", 0)),
                "in_pit": info.get("in_pit", False),
            })
        context["standings"] = standings

        # Involved driver details
        involved_codes = [driver]
        if event_type == "overtake":
            overtaken = event.get("details", {}).get("overtaken", "")
            if overtaken:
                involved_codes.append(overtaken)

        involved = {}
        for code in involved_codes:
            d = drivers.get(code, {})
            involved[_driver_name(code)] = {
                "position": d.get("position", "?"),
                "lap": d.get("lap", "?"),
                "tyre": _tyre_name_from_int(d.get("tyre", 0)),
                "tyre_life": int(d.get("tyre_life", 0)),
                "speed_kph": int(d.get("speed", 0)),
                "drs_active": d.get("drs", 0) >= 10,
            }
        context["involved_drivers"] = involved

        # Weather
        weather = closest_frame.get("weather")
        if weather:
            context["weather"] = {
                "track_temp": weather.get("track_temp"),
                "air_temp": weather.get("air_temp"),
                "rain": weather.get("rain_state", "DRY"),
            }

    # Recent events for narrative flow
    recent = []
    for e in all_events:
        if e["time"] < event_time:
            recent.append({
                "type": e["type"],
                "driver": _driver_name(e.get("driver", "")),
                "lap": e.get("lap", "?"),
                "summary": e.get("commentary", ""),
            })
    context["recent_events"] = recent[-3:]  # last 3 events before this one

    return context


def _tyre_name_from_int(tyre_int) -> str:
    """Map numeric tyre compound id to human name."""
    from src.lib.tyres import TYRE_COMPOUND_NAMES
    try:
        return TYRE_COMPOUND_NAMES.get(int(tyre_int), "UNKNOWN")
    except (ValueError, TypeError):
        return "UNKNOWN"


# ── Prompt builder ───────────────────────────────────────────────────────

def _build_user_prompt(context: dict) -> str:
    """Build the user-facing prompt from the context dict."""
    lines = []

    event_type = context.get("event_type", "event").upper().replace("_", " ")
    lines.append(f"EVENT TYPE: {event_type}")
    lines.append(f"LAP: {context.get('event_lap', '?')}")
    lines.append(f"TIME: {context.get('event_time', '?')}")
    lines.append(f"TEMPLATE: {context.get('commentary_template', '')}")
    lines.append("")

    # Event-specific details
    details = context.get("details", {})
    if details:
        lines.append("EVENT DETAILS:")
        for k, v in details.items():
            lines.append(f"  {k}: {v}")
        lines.append("")

    # Involved drivers
    involved = context.get("involved_drivers", {})
    if involved:
        lines.append("INVOLVED DRIVERS:")
        for name, info in involved.items():
            parts = [f"  {name}: P{info['position']}"]
            parts.append(f"Lap {info['lap']}")
            parts.append(f"{info['tyre']} tyres ({info['tyre_life']} laps old)")
            if info.get("drs_active"):
                parts.append("DRS OPEN")
            lines.append(", ".join(parts))
        lines.append("")

    # Standings
    standings = context.get("standings", [])
    if standings:
        lines.append("CURRENT TOP 10:")
        for s in standings:
            pit_tag = " [IN PIT]" if s.get("in_pit") else ""
            lines.append(
                f"  P{s['pos']} {s['driver']} — "
                f"{s['tyre']} ({s['tyre_life']}L){pit_tag}"
            )
        lines.append("")

    # Weather
    weather = context.get("weather")
    if weather:
        lines.append(
            f"WEATHER: {weather.get('rain', 'DRY')} | "
            f"Track {weather.get('track_temp', '?')}°C | "
            f"Air {weather.get('air_temp', '?')}°C"
        )
        lines.append("")

    # Recent events for narrative continuity
    recent = context.get("recent_events", [])
    if recent:
        lines.append("RECENT EVENTS:")
        for r in recent:
            lines.append(f"  Lap {r['lap']}: {r['summary']}")
        lines.append("")

    lines.append("Write broadcast-quality commentary for this event:")

    return "\n".join(lines)


# ── Main engine ──────────────────────────────────────────────────────────

class AICommentaryEngine:
    """
    Enrich race events with LLM-generated commentary using Google Gemini.

    Usage:
        engine = AICommentaryEngine(api_key="your-key")
        enriched_events = engine.enrich_all_events(events, frames)
    """

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        self.api_key = api_key
        self.model = model
        self._client = None
        self._init_client()

    def _init_client(self):
        """Lazily initialize the Groq client."""
        try:
            from groq import Groq
            self._client = Groq(api_key=self.api_key)
            print(f"AICommentaryEngine: Initialized with model {self.model}")
        except ImportError:
            print("AICommentaryEngine: groq package not installed. "
                  "Run: pip install groq")
            self._client = None
        except Exception as e:
            print(f"AICommentaryEngine: Failed to initialize client: {e}")
            self._client = None

    # ── Priority filter ───────────────────────────────────────────────────

    # Only overtakes involving these positions get AI commentary.
    # Everything else uses template text. This is the single biggest
    # lever for cutting API calls on high-event-count races.
    TOP_N_POSITIONS = 10   # enrich overtakes for P1-P10 only
    BATCH_SIZE = 15         # events per API call

    def _is_worth_enriching(self, event: dict) -> bool:
        """Return True if this event is worth spending an API call on."""
        etype = event.get("type", "")
        priority = event.get("priority", 3)

        # Always enrich critical events (safety car, red flag, VSC)
        if priority == 1:
            return True

        # Always enrich fastest laps
        if etype == "fastest_lap":
            return True

        # Enrich pit stops (priority 2)
        if etype == "pit_stop":
            return True

        # For overtakes: only enrich if it involves a top-N position
        if etype == "overtake":
            details = event.get("details", {})
            new_pos = details.get("new_position", 99)
            try:
                return int(new_pos) <= self.TOP_N_POSITIONS
            except (TypeError, ValueError):
                return False

        return False

    # ── Batch enrichment ──────────────────────────────────────────────────

    def _build_batch_prompt(self, batch: list[dict],
                            frames: list[dict],
                            all_events: list[dict]) -> str:
        """Build a single prompt asking Gemini to commentate on multiple events."""
        lines = [
            "You are an F1 commentator. For each numbered event below, write "
            "EXACTLY 1-2 sentences of broadcast commentary. "
            "Return ONLY a valid JSON array in this exact format (no markdown, no extra text):\n"
            '[{"id":1,"c":"commentary here"},{"id":2,"c":"commentary here"},...]\n\n'
            "Events:"
        ]

        for i, event in enumerate(batch, 1):
            etype = event.get("type", "").upper().replace("_", " ")
            lap = event.get("lap", "?")
            driver = _driver_name(event.get("driver", ""))
            template = event.get("commentary", "")
            details = event.get("details", {})

            # Add involved driver info from nearest frame
            driver_info = ""
            event_time = event.get("time", 0)
            closest = min(frames, key=lambda f: abs(f["t"] - event_time),
                         default=None) if frames else None
            if closest:
                d = closest.get("drivers", {}).get(event.get("driver", ""), {})
                if d:
                    from src.lib.tyres import TYRE_COMPOUND_NAMES
                    tyre = TYRE_COMPOUND_NAMES.get(int(d.get("tyre", 0)), "?")
                    driver_info = (f", {tyre} tyres ({int(d.get('tyre_life', 0))}L), "
                                   f"P{d.get('position', '?')}")

            detail_str = ""
            if details:
                detail_str = ", ".join(f"{k}={v}" for k, v in details.items()
                                        if k not in ("new_position",))

            lines.append(
                f"{i}. [{etype}] Lap {lap} — {driver}{driver_info}. "
                f"Template: \"{template}\""
                + (f". Details: {detail_str}" if detail_str else "")
            )

        return "\n".join(lines)

    def _enrich_batch(self, batch: list[dict],
                      frames: list[dict],
                      all_events: list[dict]) -> int:
        """
        Send one batch to Gemini, parse the JSON response, and write
        ai_commentary into each event dict in-place.

        Returns number of events successfully enriched.
        """
        if self._client is None:
            return 0

        prompt = self._build_batch_prompt(batch, frames, all_events)

        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.75,
                max_tokens=600,
            )

            if not response or not response.choices or not response.choices[0].message.content:
                return 0

            raw = response.choices[0].message.content.strip()

            # Strip any markdown code fences the model might add
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            raw = raw.strip()

            import json
            results = json.loads(raw)  # list of {"id": N, "c": "..."}

            count = 0
            for item in results:
                idx = int(item.get("id", 0)) - 1
                commentary = str(item.get("c", "")).strip()
                if 0 <= idx < len(batch) and commentary:
                    batch[idx]["ai_commentary"] = (
                        commentary.replace("**", "").replace("*", "")
                    )
                    count += 1
            return count

        except Exception as e:
            print(f"AICommentaryEngine: Batch error: {e}")
            return 0

    def enrich_key_events(self, events: list[dict],
                          frames: list[dict],
                          progress_callback=None) -> dict:
        """
        Efficiently enrich only high-value events using batched API calls.

        Workflow:
          1. Filter events to only priority 1/2 and top-N overtakes.
          2. Group into batches of BATCH_SIZE.
          3. Send one API call per batch → JSON array of commentaries.
          4. Write results back into the original event dicts in-place.

        Returns a dict with stats:
          {"total": N, "enriched": K, "skipped": S, "api_calls": C}
        """
        if self._client is None:
            return {"total": len(events), "enriched": 0,
                    "skipped": len(events), "api_calls": 0}

        # Step 1: Filter
        worth = [e for e in events if self._is_worth_enriching(e)]
        skipped = len(events) - len(worth)

        if not worth:
            return {"total": len(events), "enriched": 0,
                    "skipped": skipped, "api_calls": 0}

        # Step 2: Batch
        batches = [
            worth[i:i + self.BATCH_SIZE]
            for i in range(0, len(worth), self.BATCH_SIZE)
        ]

        print(
            f"AICommentaryEngine: Enriching {len(worth)} key events "
            f"in {len(batches)} API calls "
            f"(skipped {skipped} low-priority events)"
        )

        total_enriched = 0
        for batch_num, batch in enumerate(batches):
            enriched = self._enrich_batch(batch, frames, events)
            total_enriched += enriched

            if progress_callback:
                progress_callback(batch_num + 1, len(batches), total_enriched)

            # Polite delay between calls (avoid rate-limit on free tier)
            if batch_num < len(batches) - 1:
                time.sleep(1.5)

        api_calls = len(batches)
        print(
            f"AICommentaryEngine: Done — {total_enriched}/{len(worth)} enriched, "
            f"{api_calls} API calls used (vs {len(events)} with old approach)"
        )
        return {
            "total": len(events),
            "enriched": total_enriched,
            "skipped": skipped,
            "api_calls": api_calls,
        }

    # ── Legacy alias (kept for compatibility) ─────────────────────────────

    def enrich_all_events(self, events: list[dict],
                          frames: list[dict]) -> list[dict]:
        """Legacy alias — now calls the efficient batch method."""
        self.enrich_key_events(events, frames)
        return events



    def generate_race_summary(self, events: list[dict],
                              frames: list[dict]) -> Optional[str]:
        """
        Generate a comprehensive narrative race summary from all detected events.

        Returns a multi-paragraph race report, or None on failure.
        """
        if self._client is None:
            print("AICommentaryEngine: No client available, cannot generate summary")
            return None

        # Build the event timeline
        lines = []
        lines.append("=== RACE EVENT TIMELINE ===")

        # Group events by type for the overview
        event_counts = {}
        for e in events:
            etype = e.get("type", "unknown")
            event_counts[etype] = event_counts.get(etype, 0) + 1

        lines.append(f"Total events detected: {len(events)}")
        for etype, count in sorted(event_counts.items()):
            lines.append(f"  {etype}: {count}")
        lines.append("")

        # Full chronological event list
        lines.append("CHRONOLOGICAL EVENTS:")
        for e in events:
            ai = e.get("ai_commentary", "")
            template = e.get("commentary", "")
            text = ai or template
            details = e.get("details", {})
            detail_str = ""
            if details:
                detail_parts = [f"{k}={v}" for k, v in details.items()]
                detail_str = f" ({', '.join(detail_parts)})"
            lines.append(
                f"  Lap {e.get('lap', '?')} [{_fmt_race_time(e.get('time', 0))}] "
                f"{e.get('type', '?').upper()}: {text}{detail_str}"
            )
        lines.append("")

        # Final standings from last frame
        if frames:
            last_frame = frames[-1]
            drivers = last_frame.get("drivers", {})
            if drivers:
                sorted_drivers = sorted(
                    drivers.items(),
                    key=lambda kv: kv[1].get("position", 99)
                )
                lines.append("FINAL STANDINGS:")
                for code, info in sorted_drivers[:20]:
                    lines.append(
                        f"  P{info.get('position', '?')} "
                        f"{_driver_name(code)} ({code})"
                    )

        summary_prompt = (
            "\n".join(lines) + "\n\n"
            "---\n"
            "Write a comprehensive, engaging race summary report (4-6 paragraphs) "
            "in the style of a Formula 1 journalist. Cover:\n"
            "1. The overall race narrative and winner\n"
            "2. Key strategic decisions (pit stops, tyre choices) that shaped the result\n"
            "3. The most dramatic overtakes and battles\n"
            "4. Any safety car / VSC periods and their impact\n"
            "5. Notable performances (both good and bad)\n\n"
            "Use driver surnames, reference specific laps and data. "
            "Make it engaging and insightful — help the reader truly understand "
            "WHY the race unfolded the way it did."
        )

        summary_system = (
            "You are an expert Formula 1 journalist writing a comprehensive post-race "
            "report. Write in a professional but engaging style. Use plain text only, "
            "no markdown formatting. Use driver surnames from this mapping: "
            + ", ".join(f"{k}={v}" for k, v in DRIVER_NAMES.items())
        )

        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": summary_system},
                    {"role": "user", "content": summary_prompt}
                ],
                temperature=0.8,
                max_tokens=1000,
            )

            if response and response.choices and response.choices[0].message.content:
                summary = response.choices[0].message.content.strip()
                summary = summary.replace("**", "").replace("*", "")
                print("AICommentaryEngine: Race summary generated successfully")
                return summary

        except Exception as e:
            print(f"AICommentaryEngine: Summary generation error: {e}")

        return None
