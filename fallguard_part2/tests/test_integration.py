import numpy as np
import pytest
from pathlib import Path

from part1.contract import FrameStatus, FallState
from fg2.blur import FailClosedBlurrer
from fg2.incident_log import IncidentLogger
from fg2.app import Part2App
from fg2.adapter import convert_part1_status
from fg2.runtime_io import read_status

def test_full_integration_pipeline(tmp_path):
    runtime_dir = tmp_path / "runtime"
    blurrer = FailClosedBlurrer()
    logger = IncidentLogger(directory=str(tmp_path / "incidents"))
    app = Part2App(runtime_dir=runtime_dir, logger=logger, blurrer=blurrer)

    # 1. Normal frame with person
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    status_normal = FrameStatus(
        frame_id=1,
        timestamp_ms=1000000,
        state=FallState.NORMAL,
        reason="stable upright",
        confidence=0.05,
        person_box=[100.0, 100.0, 200.0, 300.0],
        person_count=1
    )
    msg1 = convert_part1_status(status_normal)
    bf1 = app.step(frame, msg1)
    assert bf1 is not None
    assert bf1.mode == "region"

    status_data = read_status(runtime_dir)
    assert status_data is not None
    assert status_data["state"] == "normal"
    assert status_data["video_ok"] is True

    # 2. Possible fall (triggers incident open)
    status_possible = FrameStatus(
        frame_id=2,
        timestamp_ms=1000500,
        state=FallState.POSSIBLE_FALL,
        reason="rapid descent",
        confidence=0.60,
        person_box=[100.0, 220.0, 300.0, 400.0],
        person_count=1
    )
    msg_poss = convert_part1_status(status_possible)
    app.step(frame, msg_poss)

    # 3. Confirmed fall
    status_fall = FrameStatus(
        frame_id=3,
        timestamp_ms=1001000,
        state=FallState.CONFIRMED_FALL,
        reason="sustained low posture",
        confidence=0.90,
        person_box=[100.0, 350.0, 360.0, 430.0],
        person_count=1
    )
    msg2 = convert_part1_status(status_fall)
    bf2 = app.step(frame, msg2)
    assert bf2 is not None
    assert bf2.mode == "region"

    status_data2 = read_status(runtime_dir)
    assert status_data2["state"] == "confirmed_fall"
    assert status_data2["open_incident"] is not None

    # Verify incidents log
    incidents = logger.read_all()
    assert len(incidents) > 0
    assert any(inc['event'] == 'incident_opened' for inc in incidents)
