import json, numpy as np, pytest
from fg2.incident_log import IncidentLogger, sanitize
from fg2.contract import StateMessage, AckMessage
from fg2.blur import PrivacyError
from fg2.mock_source import MockSource

def test_lifecycle_and_metadata_only(tmp_path):
    log = IncidentLogger(tmp_path, model="m1", runtime="r1")
    events = [log.observe(m) for _, m in MockSource(fps=5)]
    events = [e for e in events if e]
    assert events == ["incident_opened", "state_change", "state_change", "incident_closed",
                      "state_change", "state_change"]
    log.acknowledge(AckMessage(1.0))
    recs = log.read_all()
    assert all(r["model"] == "m1" for r in recs)
    assert recs[0]["incident_id"] and recs[-1]["event"] == "acknowledged"
    raw = (tmp_path / "incidents.jsonl").read_text()
    assert "boxes" not in raw and "image" not in raw

@pytest.mark.parametrize("bad", [{"event": "x", "boxes": [[1, 2, 3, 4]]},
                                 {"event": "x", "reason": np.zeros(3)},
                                 {"event": "x", "reason": "y" * 500},
                                 {"event": "x", "state": {"nested": 1}}])
def test_sanitize_rejects(bad):
    with pytest.raises(PrivacyError):
        sanitize(bad)

def test_no_duplicate_logs_for_same_state(tmp_path):
    log = IncidentLogger(tmp_path)
    m = StateMessage(1.0, 1, "possible_fall", "r", 0.5, 1, (), True)
    assert log.observe(m) == "incident_opened"
    assert log.observe(m) is None
