"""Quick smoke test for the RaceEventDetector."""
from src.insights.race_event_detector import RaceEventDetector

# ── Test 1: Overtake + Safety Car detection ──────────────────────────────
frames = []
for i in range(50):
    t = float(i * 0.04)
    frames.append({
        "t": t,
        "lap": 5,
        "drivers": {
            "VER": {
                "position": 1 if i < 20 else 2,
                "x": 0.0, "y": 0.0, "lap": 5,
                "drs": 12 if i > 15 else 0,
                "in_pit": False, "speed": 300,
                "tyre": 0, "tyre_life": 10, "dist": 1000 + i,
            },
            "LEC": {
                "position": 2 if i < 20 else 1,
                "x": 10.0, "y": 10.0, "lap": 5,
                "drs": 0, "in_pit": False, "speed": 295,
                "tyre": 0, "tyre_life": 10, "dist": 995 + i,
            },
        },
    })

track_statuses = [{"status": "4", "start_time": 0.5, "end_time": 1.0}]

detector = RaceEventDetector(frames, track_statuses, total_laps=50)
events = detector.detect_all()

print(f"Total events detected: {len(events)}")
for e in events:
    print(f"  [{e['type']}] {e['commentary']}")

assert len(events) >= 2, f"Expected at least 2 events, got {len(events)}"
assert any(e["type"] == "safety_car" for e in events), "Expected safety_car event"
assert any(e["type"] == "overtake" for e in events), "Expected overtake event"
print("\nAll tests PASSED")
