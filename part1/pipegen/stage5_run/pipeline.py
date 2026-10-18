"""DeepStream/PipeGen runtime integration point.

This module is intentionally explicit about the runtime boundary: PipeGen or
DeepStream supplies decoded metadata to the sidecar over stdin. The default
implementation provides a safe metadata replay mode so the temporal logic can
be validated before GPU dependencies are available.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterable


def replay(path: Path, sidecar_cmd: str) -> int:
    process = subprocess.Popen(
        sidecar_cmd,
        shell=True,
        stdin=subprocess.PIPE,
        stdout=sys.stdout,
        stderr=sys.stderr,
        text=True,
    )
    assert process.stdin is not None
    try:
        with path.open("r", encoding="utf-8") as source:
            for line in source:
                process.stdin.write(line)
                process.stdin.flush()
                time.sleep(0.01)
    finally:
        process.stdin.close()
    return process.wait()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replay", type=Path)
    parser.add_argument("--sidecar-cmd", required=True)
    parser.add_argument("--camera", type=int, default=0)
    args = parser.parse_args()
    if args.replay:
        raise SystemExit(replay(args.replay, args.sidecar_cmd))

    print(
        "PipeGen runtime hook is ready. Install PipeGen/DeepStream in the target "
        "Linux GPU container, then connect its decoder to the sidecar stdin.",
        file=sys.stderr,
    )
    print(json.dumps({"camera": args.camera, "status": "runtime-not-installed"}))
    raise SystemExit(2)


if __name__ == "__main__":
    main()
