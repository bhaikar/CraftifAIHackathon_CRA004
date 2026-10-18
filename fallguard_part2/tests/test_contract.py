import json, pytest
from fg2.contract import StateMessage, AckMessage, ContractError

GOOD = {"ts": 1.0, "frame_id": 3, "state": "normal", "reason": "ok", "evidence_score": 0.1,
        "track_id": 1, "boxes": [[1, 2, 30, 40]], "camera_ok": True}

def test_roundtrip():
    m = StateMessage.from_dict(GOOD)
    assert StateMessage.from_json(m.to_json()) == m

@pytest.mark.parametrize("patch", [
    {"state": "falling"}, {"boxes": [[5, 5, 1, 1]]}, {"boxes": [[1, 2, 3]]},
    {"frame_id": True}, {"frame_id": -1}, {"evidence_score": float("nan")},
    {"evidence_score": 1.5}, {"camera_ok": "yes"}, {"track_id": "a"}, {"reason": "x" * 201},
])
def test_rejects_bad(patch):
    with pytest.raises(ContractError):
        StateMessage.from_dict({**GOOD, **patch})

def test_missing_field():
    d = dict(GOOD); d.pop("boxes")
    with pytest.raises(ContractError):
        StateMessage.from_dict(d)

def test_bad_json():
    with pytest.raises(ContractError):
        StateMessage.from_json("{not json")

def test_ack():
    assert AckMessage.from_json(AckMessage(5.0).to_json()).ts == 5.0
    with pytest.raises(ContractError):
        AckMessage.from_json(json.dumps({"cmd": "reset", "ts": 1}))
