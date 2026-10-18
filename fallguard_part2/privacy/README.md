# Privacy policy for the FallGuard prototype

## What is processed
Camera frames are processed locally, in memory, on the demo machine. Nothing is sent to a cloud service.

## What is stored
| Item | Location | Contents | Retention |
|---|---|---|---|
| Incident log | `incidents/incidents.jsonl` | Timestamp, event, state, reason text, evidence score, track id, frame id, model/runtime names, operator action. Whitelisted scalar fields only; anything else is rejected in code. | Delete after judging |
| Latest preview | `runtime/latest_blurred.jpg` | One blurred frame, overwritten continuously | Overwritten every frame; deleted when blurring fails; delete the folder after the demo |
| Status and ack | `runtime/status.json`, `runtime/ack.json` | State, reason, score, flags | Overwritten; delete after the demo |

Never stored: raw frames, raw video, audio, identity data, face crops.
Video recording is off. Blurred incident clips and RTSP streaming are not implemented yet, and when added must write only blurred frames.

## What is sent over MQTT
`care/room1/fall` carries event, incident id, timestamp, state, reason, evidence score and track id. No frames, no boxes.
`care/room1/status` carries `online` or `offline` (last-will). `care/room1/ack` carries the operator acknowledgement.

## Blur rules (fail-closed)
1. A frame is blurred only against boxes tied to that exact frame id. Otherwise the whole frame is blurred.
2. Holding old boxes is off by default because it leaked when posture changed quickly (measured by the audit).
3. Camera fault, boxes outside the frame, or no detector data means a full-frame blur.
4. If the blur step raises an error, nothing is emitted and the previous preview is deleted.
5. Output sinks accept only `BlurredFrame` objects, which only the blurrer can create.
6. Empty-scene policy defaults to a full blur. Switching it to `passthrough_when_healthy` accepts the risk that a missed detection shows an unblurred person.

## Limits
Pixelation was tested on synthetic frames. It has not been tested against face recognition on real footage. Faces in screenshots for the submission should still be avoided.
This is an assistive demo and not a validated medical alarm. Every alert asks a human to check on the person; nothing contacts emergency services.

## How to reproduce the evidence
    python tools/privacy_audit.py --run-tests
This writes `privacy/PRIVACY_TEST_REPORT.md` from measured results on your machine. Re-run after any change to `blur.py`.
