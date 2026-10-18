# PipeGen Stage 3 — Pose model

## Candidate

**Ultralytics YOLO pose ONNX, COCO-17 output** is the first candidate because
one inference produces person detections and 17 keypoints. The model output
must be adapted to the normalized parser payload used by `fallguard.adapter`.

## Acceptance checks

- [ ] ONNX input shape and channel order recorded here.
- [ ] Preprocessing (letterbox/resize, RGB/BGR, scale) matches export.
- [ ] Keypoint order verified as COCO-17.
- [ ] Parser emits `[x1, y1, x2, y2]`, 17 `[x, y, confidence]` rows, score.
- [ ] Model license and source URL copied into `license-note.md`.

Do not claim model selection is complete until the parser check is captured in
the evidence folder. If the selected pose model does not expose reliable boxes,
add a separate person detector as a documented fallback rather than silently
assuming the box is available.
