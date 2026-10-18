from fallguard.features import extract_features
from fallguard.state_machine import FallStateMachine
from contract import FallState


def pose(upright: bool = True, confidence: float = 0.95):
    # Coordinates are synthetic but preserve shoulder/hip geometry.
    if upright:
        pts = [[100, 100, confidence] for _ in range(17)]
        pts[5] = [90, 100, confidence]
        pts[6] = [110, 100, confidence]
        pts[11] = [90, 200, confidence]
        pts[12] = [110, 200, confidence]
        return pts
    pts = [[100, 100, confidence] for _ in range(17)]
    pts[5] = [100, 100, confidence]
    pts[6] = [200, 100, confidence]
    pts[11] = [300, 110, confidence]
    pts[12] = [400, 110, confidence]
    return pts


def box(upright: bool = True):
    return [50, 50, 150, 250] if upright else [50, 50, 450, 150]


def test_quick_recovery_returns_to_normal():
    machine = FallStateMachine(confirmation_window_seconds=3)
    upright = extract_features(pose(True), box(True))
    horizontal = extract_features(pose(False), box(False))
    assert machine.update(0, upright).state is FallState.NORMAL
    assert machine.update(100, horizontal).state is FallState.POSSIBLE_FALL
    assert machine.update(500, upright).state is FallState.NORMAL


def test_persistent_horizontal_pose_confirms_then_recovers():
    machine = FallStateMachine(confirmation_window_seconds=3, upright_recovery_seconds=1)
    upright = extract_features(pose(True), box(True))
    horizontal = extract_features(pose(False), box(False))
    assert machine.update(0, upright).state is FallState.NORMAL
    machine.update(100, horizontal)
    machine.update(1000, horizontal)
    machine.update(2000, horizontal)
    assert machine.update(3200, horizontal).state is FallState.CONFIRMED_FALL
    machine.update(3300, upright)
    assert machine.update(4500, upright).state is FallState.RECOVERING
    assert machine.acknowledge(4500).state is FallState.NORMAL


def test_low_confidence_is_unknown():
    machine = FallStateMachine()
    low = extract_features(pose(True, 0.1), box(True))
    assert machine.update(0, low).state is FallState.UNKNOWN
