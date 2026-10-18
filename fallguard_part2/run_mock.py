"""Run Part 2 end to end against the mock producer. Then: streamlit run dashboard/app.py"""
import argparse, dataclasses, json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))
from fg2.alerts import AlertPublisher
from fg2.app import Part2App
from fg2.blur import BlurConfig, FailClosedBlurrer
from fg2.bus import LocalBus, MqttBus
from fg2.incident_log import IncidentLogger
from fg2.mock_source import MockSource

ap = argparse.ArgumentParser()
ap.add_argument("--fps", type=int, default=15)
ap.add_argument("--runtime", default="runtime")
ap.add_argument("--mqtt-host", default=None, help="e.g. localhost; omit to run without a broker")
ap.add_argument("--mqtt-port", type=int, default=1883)
ap.add_argument("--loops", type=int, default=1)
a = ap.parse_args()

cfg = json.loads((Path(__file__).parent / "config/part2.json").read_text())
bus = MqttBus(a.mqtt_host, a.mqtt_port) if a.mqtt_host else LocalBus()
if a.mqtt_host:
    bus.start()
logger = IncidentLogger(cfg["incident_dir"], "mock-producer", "mock")   # mock data must never look like real pipeline data
app = Part2App(a.runtime, logger, FailClosedBlurrer(BlurConfig(**cfg["blur"])), AlertPublisher(bus), bus)
print(f"running; runtime dir = {a.runtime}. Acknowledge from the dashboard when the fall is confirmed.")
t0, n, worst = time.perf_counter(), 0, 0.0
for _ in range(a.loops):
    for frame, msg in MockSource(fps=a.fps, hold_until_ack=lambda: app.acked):
        msg = dataclasses.replace(msg, ts=time.time())      # capture time, like a real pipeline
        app.step(frame, msg)
        n += 1
        slack = t0 + n / a.fps - time.perf_counter()
        worst = min(worst, slack)
        if slack > 0:
            time.sleep(slack)
print(f"{n} frames; worst pacing lag {-worst * 1000:.0f} ms (0 means the machine kept up with {a.fps} fps)")
bus.close()
