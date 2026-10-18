"""Download/convert hook for the selected pose model.

The exact model URL is intentionally supplied by the runtime operator after
license review. This script records a SHA-256 once a local ONNX file exists.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("onnx", type=Path)
    args = parser.parse_args()
    if not args.onnx.exists():
        raise SystemExit(f"ONNX file does not exist: {args.onnx}")
    print(f"model={args.onnx.resolve()}")
    print(f"sha256={sha256(args.onnx)}")


if __name__ == "__main__":
    main()
