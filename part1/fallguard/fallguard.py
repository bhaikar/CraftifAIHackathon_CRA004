"""FallGuard sidecar entry point.

Input is newline-delimited JSON from PipeGen's metadata bridge. Output is one
newline-delimited contract message per input frame. Raw video never crosses
this process boundary.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path
from typing import Any

from contract import FrameStatus
from .adapter import decode_pose_output, select_single_person
from .features import extract_features
from .state_machine import FallStateMachine
from .watchdog import FeedWatchdog


def process_frame(
    payload: dict[str, Any],
    machine: FallStateMachine,
    watchdog: FeedWatchdog,
) -> FrameStatus:
    frame_id = int(payload.get("frame_id", 0))
    timestamp_ms = int(payload.get("timestamp_ms", time.time_ns() // 1_000_000))
    watchdog.observe(timestamp_ms)
    detections = decode_pose_output(payload)
    selected, selection_reason = select_single_person(detections)
    if selected is None:
        update = machine.update(timestamp_ms, None, reliable=False, person_count=len(detections))
        return FrameStatus(frame_id, timestamp_ms, update.state, selection_reason, update.confidence,
                           person_count=len(detections))

    features = extract_features(selected.keypoints, selected.box)
    update = machine.update(timestamp_ms, features, reliable=True, person_count=1)
    return FrameStatus(
        frame_id=frame_id,
        timestamp_ms=timestamp_ms,
        state=update.state,
        reason=update.reason,
        confidence=update.confidence,
        person_box=selected.box,
        keypoints=selected.keypoints,
        person_count=1,
        metrics={
            "torso_length": features.torso_length,
            "trunk_angle_deg": features.trunk_angle_deg,
            "body_aspect_ratio": features.body_aspect_ratio,
        },
    )


def run_stream(input_stream: Any, output_stream: Any, event_log: Path | None = None) -> None:
    machine = FallStateMachine()
    watchdog = FeedWatchdog()
    writer = None
    log_handle = None
    if event_log:
        event_log.parent.mkdir(parents=True, exist_ok=True)
        log_handle = event_log.open("a", newline="", encoding="utf-8")
        writer = csv.DictWriter(log_handle, fieldnames=["frame_id", "timestamp_ms", "state", "reason", "confidence"])
        if log_handle.tell() == 0:
            writer.writeheader()
    try:
        for line in input_stream:
            if not line.strip():
                continue
            try:
                status = process_frame(json.loads(line), machine, watchdog)
                output_stream.write(status.to_json() + "\n")
                output_stream.flush()
                if writer:
                    writer.writerow({
                        "frame_id": status.frame_id,
                        "timestamp_ms": status.timestamp_ms,
                        "state": status.state.value,
                        "reason": status.reason,
                        "confidence": f"{status.confidence:.4f}",
                    })
                    log_handle.flush()
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                error = {"state": "Unknown", "reason": f"invalid metadata: {exc}"}
                output_stream.write(json.dumps(error) + "\n")
                output_stream.flush()
    finally:
        if log_handle:
            log_handle.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="FallGuard keypoint-to-state sidecar")
    parser.add_argument("--event-log", type=Path, default=None)
    args = parser.parse_args()
    run_stream(sys.stdin, sys.stdout, args.event_log)


if __name__ == "__main__":
    main()
