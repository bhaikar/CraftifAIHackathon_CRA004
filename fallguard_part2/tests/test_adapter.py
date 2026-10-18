import pytest
from part1.contract import FrameStatus, FallState
from fg2.adapter import convert_part1_status
from fg2.contract import StateMessage

def test_adapter_state_mapping():
    for f_state, expected_str in [
        (FallState.NORMAL, "normal"),
        (FallState.POSSIBLE_FALL, "possible_fall"),
        (FallState.CONFIRMED_FALL, "confirmed_fall"),
        (FallState.RECOVERING, "recovering"),
        (FallState.UNKNOWN, "unknown"),
    ]:
        status = FrameStatus(
            frame_id=1,
            timestamp_ms=15000,
            state=f_state,
            reason="test reason",
            confidence=0.5,
            person_box=[10.0, 20.0, 100.0, 200.0]
        )
        msg = convert_part1_status(status)
        assert msg.state == expected_str
        assert msg.ts == 15.0
        assert msg.frame_id == 1
        assert msg.boxes == ((10.0, 20.0, 100.0, 200.0),)
        assert msg.camera_ok is True

def test_adapter_camera_fault():
    status = FrameStatus(
        frame_id=2,
        timestamp_ms=20000,
        state=FallState.UNKNOWN,
        reason="camera lost connection",
        confidence=0.0,
        person_box=None
    )
    msg = convert_part1_status(status)
    assert msg.state == "unknown"
    assert msg.camera_ok is False
    assert msg.boxes == ()
