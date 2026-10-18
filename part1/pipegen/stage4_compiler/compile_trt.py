"""TensorRT FP16 compiler wrapper.

Run this inside the CUDA/TensorRT container. The command and output are
captured verbatim into evidence/compiler-log.txt by default.
"""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("onnx", type=Path)
    parser.add_argument("--engine", type=Path, default=Path("pose_fp16.engine"))
    parser.add_argument("--workspace", type=int, default=4096)
    parser.add_argument("--log", type=Path, default=Path("../../evidence/compiler-log.txt"))
    args = parser.parse_args()

    command = [
        "trtexec",
        f"--onnx={args.onnx}",
        f"--saveEngine={args.engine}",
        "--fp16",
        f"--workspace={args.workspace}",
        "--verbose",
    ]
    args.log.parent.mkdir(parents=True, exist_ok=True)
    with args.log.open("w", encoding="utf-8") as log:
        log.write("$ " + " ".join(command) + "\n\n")
        completed = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, text=True, check=False)
        log.write(f"\nexit_code={completed.returncode}\n")
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)
    print(f"Wrote {args.engine}")


if __name__ == "__main__":
    main()
