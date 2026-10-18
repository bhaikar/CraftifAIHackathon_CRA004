"""End-to-end integration runner for Part 1 (FallGuard pipeline/state machine) and Part 2 (Privacy Blur, Incidents, Dashboard)."""
from __future__ import annotations
import time
import numpy as np
from pathlib import Path

from part1.contract import FrameStatus, FallState
from part1.fallguard.state_machine import FallStateMachine
from part1.fallguard.features import PoseFeatures
from fg2.blur import FailClosedBlurrer, BlurConfig
from fg2.incident_log import IncidentLogger
from fg2.app import Part2App
from fg2.adapter import convert_part1_status
from fg2.mock_source import MockSource


def run_integration_demo(runtime_dir="runtime", max_frames=150):
    print("Initializing FallGuard Integration Demo...")
    runtime_path = Path(runtime_dir)
    runtime_path.mkdir(parents=True, exist_ok=True)

    blurrer = FailClosedBlurrer()
    logger = IncidentLogger(directory=str(runtime_path / "incidents"), model="fallguard-hybrid", runtime="cpu-mock")
    app = Part2App(runtime_dir=runtime_path, logger=logger, blurrer=blurrer)
    machine = FallStateMachine()

    mock_source = MockSource(fps=10)
    print(f"Running simulation up to {max_frames} frames...")

    count = 0
    for frame, state_msg in mock_source:
        if count >= max_frames:
            break

        # Simulate Part 1 processing or feed state_msg via adapter
        # Here we convert mock state message to Part 1 FrameStatus then back via adapter
        # Or test with FallStateMachine directly
        f_state = FallState.NORMAL
        if state_msg.state == "possible_fall":
            f_state = FallState.POSSIBLE_FALL
        elif state_msg.state == "confirmed_fall":
            f_state = FallState.CONFIRMED_FALL
        elif state_msg.state == "recovering":
            f_state = FallState.RECOVERING
        elif state_msg.state == "unknown":
            f_state = FallState.UNKNOWN

        box = list(state_msg.boxes[0]) if state_msg.boxes else None
        status = FrameStatus(
            frame_id=state_msg.frame_id,
            timestamp_ms=int(state_msg.ts * 1000),
            state=f_state,
            reason=state_msg.reason,
            confidence=state_msg.evidence_score,
            person_box=box,
            person_count=1 if box else 0
        )

        part2_msg = convert_part1_status(status, camera_ok=state_msg.camera_ok)
        bf = app.step(frame, part2_msg)

        if count % 20 == 0:
            print(f"Frame {state_msg.frame_id:3d} | State: {part2_msg.state:15s} | Blur Mode: {bf.mode if bf else 'dropped'}")

        count += 1

    print(f"Integration run completed successfully. Processed {count} frames.")
    print(f"Incidents logged: {len(logger.read_all())}")
    print(f"Latest blurred image written to: {runtime_path / 'latest_blurred.jpg'}")


if __name__ == "__main__":
    run_integration_demo()
