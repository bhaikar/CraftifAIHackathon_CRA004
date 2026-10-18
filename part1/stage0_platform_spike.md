# G0 platform spike

Run this checklist before claiming a live GPU result. Record the outputs in
`evidence/platform-report.md`; do not replace missing values with guesses.

## Host capture

```bash
uname -a
nvidia-smi
python3 --version
docker version
xhost
```

## PipeGen runtime

```bash
pipegen --version
python3 -c "import gi; print('PyGObject OK')"
python3 -c "import pyds; print('DeepStream Python bindings OK')"
```

## Live frame acceptance

1. Start the runtime with `./run.sh`.
2. Verify the preview shows a live webcam frame.
3. Verify the sidecar receives increasing `frame_id` and `timestamp_ms`.
4. Capture the terminal output and preview screenshot under `evidence/g0/`.

The Windows host is not itself the target DeepStream environment. The intended
runtime is an NVIDIA Linux container/VM with GPU passthrough and X11 display.
