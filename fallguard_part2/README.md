# FallGuard Part 2: privacy, alerts, app (M1 + M2)

Setup (Windows PowerShell, inside this folder):
    python -m venv .venv ; .\.venv\Scripts\Activate.ps1
    python -m pip install numpy opencv-python-headless paho-mqtt streamlit pytest
    python -m pytest -q

Demo without Part 1 (two terminals, venv active in both):
    python run_mock.py                      # mock producer -> blur -> log -> alerts -> runtime/
    streamlit run dashboard/app.py          # open the URL, press Acknowledge when the fall is confirmed

With an MQTT broker (Mosquitto): `python run_mock.py --mqtt-host localhost`
and set `$env:FG2_MQTT_HOST="localhost"` before starting the dashboard so Acknowledge also publishes on care/room1/ack.

| Module | Purpose |
|---|---|
| fg2/contract.py | Message schema, validation, topics (care/room1/state, fall, ack, status) |
| fg2/blur.py | Fail-closed blur; sinks must call require_blurred() |
| fg2/incident_log.py | Metadata-only JSONL incident log with field whitelist |
| fg2/alerts.py | MQTT alerts on care/room1/fall (fall_alert, alert_cleared) |
| fg2/bus.py | MqttBus (last-will, retained online status) and LocalBus |
| fg2/runtime_io.py | File channel to dashboard: blurred JPEG, status.json, ack.json |
| fg2/app.py | Controller: step(frame, msg) -> blurred frame, log, alert, status |
| fg2/mock_source.py | Fake Part 1 producer, can hold Confirmed until acknowledged |
| tools/privacy_audit.py | Runs privacy failure scenarios and writes privacy/PRIVACY_TEST_REPORT.md |
| dashboard/app.py | Streamlit dashboard: state, reason, video, incidents, Acknowledge |

Integration with Part 1: call `Part2App.step(frame, StateMessage)` per frame. Part 1 must also listen on
care/room1/ack to leave Confirmed fall. Empty-scene policy defaults to full_blur and hold_frames to 0 (strictest; see privacy/README.md).
