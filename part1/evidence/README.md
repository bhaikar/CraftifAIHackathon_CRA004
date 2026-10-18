# Evidence index

This folder is intentionally free of fabricated benchmark values. Populate it
with real captures from the target runtime:

- `g0/platform-report.md` — OS, GPU, driver, Docker, X11, PipeGen version,
  live-frame acceptance.
- `stage1-requirement.png` — Requirement stage screenshot.
- `stage2-pipeline-ir.png` — Pipeline IR/node graph screenshot.
- `stage3-model.md` — model URL, license, SHA-256, parser verification.
- `compiler-log.txt` — full TensorRT `trtexec --fp16` output.
- `pose_fp16.engine` — compiled engine export.
- `speed-report.json` — original PipeGen final-run speed report.
- `run-screenshot.png` — live preview and state output (debug-only preview).
- `scenario-test-log.csv` — scenario matrix with measured results.

Never present a placeholder or debug preview as a validated live GPU result.
