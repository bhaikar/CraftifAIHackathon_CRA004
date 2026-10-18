# FallGuard Part 2: Privacy, Incidents, Dashboard & Integration

## Quick Start (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:PYTHONPATH=".;part1;fallguard_part2/src"
```

## Running the Integration Simulation & Dashboard

1. **Run the integration simulation runner** (generates runtime state and incident records):
   ```powershell
   python fallguard_part2/run_integration.py
   ```

2. **Launch the operator dashboard**:
   ```powershell
   streamlit run fallguard_part2/dashboard/app.py
   ```

## Standard Runtime Paths

- Runtime state: `runtime/status.json`, `runtime/latest_blurred.jpg`, `runtime/ack.json`
- Incident log: `runtime/incidents/incidents.jsonl`

## Architecture & Modules

| Module | Purpose |
|---|---|
| `fg2/contract.py` | Message schema, validation, topics |
| `fg2/blur.py` | Fail-closed blur; sinks call `require_blurred()` |
| `fg2/incident_log.py` | Metadata-only JSONL incident log with field whitelist |
| `fg2/alerts.py` | MQTT alerts on `care/room1/fall` |
| `fg2/bus.py` | MqttBus and LocalBus |
| `fg2/runtime_io.py` | File channel to dashboard |
| `fg2/app.py` | Controller: `step(frame, msg)` |
| `fg2/adapter.py` | Bridges Part 1 `FrameStatus` to Part 2 `StateMessage` |
| `dashboard/app.py` | Streamlit control-room dashboard |
| `tools/privacy_audit.py` | Runs privacy failure scenarios |

## Limitations

- **Simulation Mode**: Local runs use CPU mock frames and synthetic keypoint traces. Live NVIDIA TensorRT/DeepStream GPU operation requires the target G0 Linux environment.
- **Acknowledgement Loop**: Dashboard acknowledgement writes `ack.json` / MQTT ack messages, which Part 2 logs. State machine re-arming requires upstream consumption of ACK messages by Part 1's state machine.
