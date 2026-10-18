import json, os, time
from pathlib import Path
import numpy as np, pytest
from fg2.alerts import AlertPublisher
from fg2.app import Part2App
from fg2.blur import FailClosedBlurrer, PrivacyError
from fg2.bus import LocalBus, MqttBus
from fg2.contract import TOPIC_FALL, TOPIC_ACK, TOPIC_STATUS, AckMessage
from fg2.incident_log import IncidentLogger, ALLOWED
from fg2.mock_source import MockSource
from fg2.runtime_io import (read_status, read_latest, write_latest, request_ack, poll_ack, clear_latest)

def detail(img):
    return float(np.abs(np.diff(img.astype(np.int16), axis=1)).mean())

def make_app(tmp_path, bus=None):
    bus = bus or LocalBus()
    app = Part2App(tmp_path / "rt", IncidentLogger(tmp_path / "inc", "m", "r"),
                   FailClosedBlurrer(), AlertPublisher(bus), bus)
    return app, bus

def test_alert_publisher_events_and_privacy(tmp_path):
    app, bus = make_app(tmp_path)
    for f, m in MockSource(fps=5, hold_until_ack=lambda: True):
        app.step(f, m)
    alerts = [json.loads(p) for t, p in bus.sent if t == TOPIC_FALL]
    assert [a["event"] for a in alerts] == ["fall_alert", "fall_alert", "alert_cleared"]
    assert [a["state"] for a in alerts][:2] == ["possible_fall", "confirmed_fall"]
    for a in alerts:
        assert set(a) <= ALLOWED and "boxes" not in a

def test_ack_loop_via_file_and_dashboard_state(tmp_path):
    app, _ = make_app(tmp_path)
    states, acked_at = [], None
    for i, (f, m) in enumerate(MockSource(fps=10, hold_until_ack=lambda: app.acked, max_hold_s=5)):
        app.step(f, m)
        states.append(m.state)
        st = read_status(tmp_path / "rt")
        if m.state == "confirmed_fall":
            assert st["awaiting_ack"] is (acked_at is None)
            if acked_at is None and states.count("confirmed_fall") > 40:
                request_ack(tmp_path / "rt"); acked_at = i
        if acked_at and m.state == "recovering":
            break
    assert acked_at and "recovering" in states
    evs = [r["event"] for r in app.logger.read_all()]
    assert evs.count("acknowledged") == 1

def test_ack_deduplicated_across_file_and_mqtt(tmp_path):
    app, bus = make_app(tmp_path)
    ack = AckMessage(123.0)
    bus.publish(TOPIC_ACK, ack.to_json())
    (tmp_path / "rt" / "ack.json").write_text(json.dumps({**json.loads(ack.to_json()), "id": "x"}))
    f, m = next(iter(MockSource(fps=5)))
    app.step(f, m)
    assert [r["event"] for r in app.logger.read_all()].count("acknowledged") == 1

def test_latest_image_is_blurred_and_raw_refused(tmp_path):
    app, _ = make_app(tmp_path)
    f, m = next(iter(MockSource(fps=5)))
    app.step(f, m)
    import cv2
    img = cv2.imdecode(np.frombuffer(read_latest(tmp_path / "rt"), np.uint8), cv2.IMREAD_COLOR)
    x1, y1, x2, y2 = (int(v) for v in m.boxes[0])
    assert detail(img[y1:y2, x1:x2]) < 0.2 * detail(f[y1:y2, x1:x2])
    with pytest.raises(PrivacyError):
        write_latest(tmp_path, f)

def test_blur_failure_withholds_output(tmp_path):
    app, _ = make_app(tmp_path)
    it = iter(MockSource(fps=5))
    f, m = next(it); app.step(f, m)
    assert read_latest(tmp_path / "rt")
    app.blurrer.process_or_drop = lambda *a, **k: None
    f, m = next(it); app.step(f, m)
    st = read_status(tmp_path / "rt")
    assert read_latest(tmp_path / "rt") is None and st["video_ok"] is False and st["blur_mode"] == "dropped"

def test_camera_loss_state_shows_no_clean_video(tmp_path):
    app, _ = make_app(tmp_path)
    for f, m in MockSource(fps=5, hold_until_ack=lambda: True):
        bf = app.step(f, m)
        if m.state == "unknown":
            st = read_status(tmp_path / "rt")
            assert st["camera_ok"] is False and bf.mode == "full"
            return
    pytest.fail("never reached unknown")

class FakeClient:
    def __init__(self): self.calls, self.subs = [], []
    def will_set(self, *a, **k): self.calls.append(("will", a, k))
    def connect_async(self, *a): pass
    def loop_start(self): pass
    def loop_stop(self): pass
    def disconnect(self): pass
    def subscribe(self, t, qos=0): self.subs.append(t)
    def publish(self, t, p, qos=0, retain=False):
        self.calls.append(("pub", t, p, retain))
        class R: rc = 0
        return R()

def test_mqtt_bus_will_online_and_dispatch():
    fc = FakeClient()
    bus = MqttBus(client=fc)
    assert fc.calls[0][0] == "will" and fc.calls[0][1][:2] == (TOPIC_STATUS, "offline") and fc.calls[0][2]["retain"]
    got = []
    bus.subscribe(TOPIC_ACK, lambda t, p: got.append(p))
    bus._on_connect(fc, None, None, 0)
    assert TOPIC_ACK in fc.subs and ("pub", TOPIC_STATUS, "online", True) in fc.calls
    class M: topic = TOPIC_ACK; payload = b'{"cmd":"ack","ts":1}'
    bus._on_message(fc, None, M)
    assert got == ['{"cmd":"ack","ts":1}']
    bus._on_disconnect(fc, None)
    assert bus.connected is False

def test_dashboard_smoke_and_stale(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv("FG2_RUNTIME", str(tmp_path / "rt"))
    monkeypatch.setenv("FG2_INCIDENTS", str(tmp_path / "inc"))
    root = Path(__file__).resolve().parent.parent
    at = AppTest.from_file(str(root / "dashboard" / "app.py"), default_timeout=15).run()
    assert not at.exception and any("stalled" in w.value for w in at.warning)   # no data: never shows Normal
    app, _ = make_app(tmp_path)
    for f, m in MockSource(fps=5):
        if m.state == "confirmed_fall":
            app.step(f, m); break
        app.step(f, m)
    at = AppTest.from_file(str(root / "dashboard" / "app.py"), default_timeout=15).run()
    assert not at.exception and any("CONFIRMED FALL" in e.value for e in at.error)
    assert at.button[0].disabled is False
    # stale status must not look current
    st = read_status(tmp_path / "rt"); st["updated_at"] = time.time() - 30
    (tmp_path / "rt" / "status.json").write_text(json.dumps(st))
    at = AppTest.from_file(str(root / "dashboard" / "app.py"), default_timeout=15).run()
    assert any("stalled" in w.value for w in at.warning) and not at.error

def test_is_stale():
    from fg2.runtime_io import is_stale
    assert is_stale(None)
    assert is_stale({"updated_at": 100.0}, now=104.0, ttl=3.0)
    assert not is_stale({"updated_at": 100.0}, now=102.0, ttl=3.0)
