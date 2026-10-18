# PipeGen Stage 1 — Requirement

## Input

- One webcam stream, timestamped frames.
- Default policy is single person.

## Inference

- COCO-17 pose ONNX model with person boxes and keypoints.
- TensorRT FP16 primary compile target.
- Input resize and normalization must match the selected model card.

## Output contract

One metadata message per frame containing frame ID, timestamp, person box,
COCO-17 keypoints and confidence. No raw video is sent to FallGuard.

## Temporal behavior

FallGuard emits `Normal`, `Possible Fall`, `Confirmed Fall`, `Recovering`, or
`Unknown`. Confirmation starts at 3 seconds and is tuned on camera. Unknown is
used for stale feed, low confidence, zero people, and multiple people.
