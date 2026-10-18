# CRAFTIFAI Part 1 — FallGuard

GPU pose inference and a temporal fall state machine, from camera metadata to
one per-frame status contract.

## Current boundary

The Python sidecar and replayable state machine are implemented and testable on
any machine. PipeGen v0.5.1 / DeepStream / TensorRT remain runtime dependencies
that must be installed in the target NVIDIA Linux container for G0 and stages
1–5 evidence. This Windows checkout does not pretend that those artifacts have
been generated.

## Quickstart: sidecar replay

```powershell
cd part1
python -m pytest -q
Get-Content .\sample-input.jsonl | python -m fallguard.fallguard --event-log evidence\event-log.csv
```

## GPU path

1. Complete `stage0_platform_spike.md` in the NVIDIA Linux runtime.
2. Select and license-review one COCO-17 pose ONNX model.
3. Run `pipegen/stage4_compiler/compile_trt.py model.onnx` with `trtexec`.
4. Connect PipeGen's decoded metadata bridge to `fallguard.fallguard`.
5. Capture every stage in `evidence/` and replace only the pending scenario rows
   with measured results.

The preview node is marked debug-only. Raw video is never part of the sidecar
contract; `person_box` is exposed specifically for Part 2 privacy blur.
