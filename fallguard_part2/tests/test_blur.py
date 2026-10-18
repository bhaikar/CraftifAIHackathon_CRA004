import numpy as np, pytest
from fg2.blur import FailClosedBlurrer, BlurConfig, BlurredFrame, PrivacyError, require_blurred
from fg2.contract import StateMessage

def frame(seed=1):
    return np.random.default_rng(seed).integers(0, 255, (480, 640, 3), dtype=np.uint8)

def msg(fid, boxes=((200, 100, 300, 300),), cam=True, ts=10.0):
    return StateMessage(ts, fid, "normal", "t", 0.0, 1 if boxes else None, tuple(boxes), cam)

def changed_fraction(a, b):
    return float(np.mean(a != b))

def test_region_blur_only_person_area():
    f, b = frame(), FailClosedBlurrer()
    r = b.process(f, 1, 10.0, msg(1))
    assert r.mode == "region" and r.image is not f
    assert r.image[100:300, 200:300].std() < 0.3 * f[100:300, 200:300].std()
    assert np.array_equal(r.image[:, :100], f[:, :100])

def test_never_returns_raw_input():
    f, b = frame(), FailClosedBlurrer()
    for m in (msg(1), None, msg(9), msg(1, cam=False)):
        r = b.process_or_drop(f, 1, 10.0, m)
        assert r is not None and r.image is not f

def test_hold_then_full():
    f, b = frame(), FailClosedBlurrer(BlurConfig(hold_frames=3))
    b.process(f, 1, 10.0, msg(1))
    modes = [b.process(f, 2 + i, 10.1 + i * 0.05, None).mode for i in range(5)]
    assert modes == ["held", "held", "held", "full", "full"]

def test_full_blur_when_boxes_for_other_frame():
    f, b = frame(), FailClosedBlurrer()
    r = b.process(f, 5, 10.0, msg(4))
    assert r.mode == "full" and changed_fraction(r.image, f) > 0.9

def test_camera_fault_full_blur():
    r = FailClosedBlurrer().process(frame(), 1, 10.0, msg(1, cam=False))
    assert r.mode == "full"

def test_boxes_outside_frame_full_blur():
    r = FailClosedBlurrer().process(frame(), 1, 10.0, msg(1, boxes=((900, 900, 950, 950),)))
    assert r.mode == "full"

def test_person_recently_seen_zero_boxes_not_passthrough():
    f = frame()
    b = FailClosedBlurrer(BlurConfig(empty_scene_policy="passthrough_when_healthy", hold_frames=0))
    b.process(f, 1, 10.0, msg(1))
    assert b.process(f, 2, 10.1, msg(2, boxes=(), ts=10.1)).mode == "full"

def test_empty_scene_policies():
    f = frame()
    assert FailClosedBlurrer().process(f, 1, 10.0, msg(1, boxes=())).mode == "full"
    pt = FailClosedBlurrer(BlurConfig(empty_scene_policy="passthrough_when_healthy"))
    assert pt.process(f, 1, 10.0, msg(1, boxes=())).mode == "empty_scene"
    assert pt.process(f, 2, 10.1, None).mode == "full"

def test_exception_drops_output():
    b = FailClosedBlurrer()
    assert b.process_or_drop(None, 1, 10.0, msg(1)) is None
    assert b.process_or_drop(np.zeros((4, 4), np.uint8), 1, 10.0, msg(1)) is None
    assert b.errors == 2

def test_sinks_reject_raw_frames():
    with pytest.raises(PrivacyError):
        require_blurred(frame())
    with pytest.raises(PrivacyError):
        BlurredFrame(frame(), "x", "y", 1, 1.0)
    require_blurred(FailClosedBlurrer().process(frame(), 1, 10.0, msg(1)))
