"""FallGuard operator dashboard. Run from the project root: streamlit run dashboard/app.py"""
import os, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import streamlit as st
from fg2.incident_log import IncidentLogger
from fg2.runtime_io import read_status, read_latest, request_ack, is_stale, STALE_AFTER_S

RUNTIME = Path(os.environ.get("FG2_RUNTIME", "runtime"))
INCIDENTS = Path(os.environ.get("FG2_INCIDENTS", "incidents"))
MQTT_HOST = os.environ.get("FG2_MQTT_HOST") or None

UI = {
    "normal": ("success", "Monitoring - no action required."),
    "possible_fall": ("warning", "Please check the person. Continue evaluating; do not dispatch automatically."),
    "confirmed_fall": ("error", "Fall-like event detected. Check on the person and acknowledge."),
    "recovering": ("info", "Recovery detected. Review and acknowledge the event, then monitoring resumes."),
    "unknown": ("warning", "Detection unavailable - check camera / scene."),
}

st.set_page_config(page_title="FallGuard AI", layout="wide")
st.title("FallGuard AI")
st.caption("Assistive demo only. Not a validated medical alarm. Video is blurred before display; nothing raw is stored.")


@st.fragment(run_every=1)
def live():
    status = read_status(RUNTIME)
    now = time.time()
    stale = is_stale(status, now, STALE_AFTER_S)
    left, right = st.columns([3, 2])
    with left:
        if stale:
            st.warning("Pipeline stalled or not running - detection unavailable. Last state is not current.")
        else:
            level, text = UI[status["state"]]
            getattr(st, level)(f"**{status['state'].replace('_', ' ').upper()}** - {text}")
        img = None if stale or not status.get("video_ok") else read_latest(RUNTIME)
        if img:
            st.image(img, caption=f"Blurred feed ({status.get('blur_mode')})", use_container_width=True)
        else:
            st.info("No video: output is withheld when blurring cannot be guaranteed.")
    with right:
        if status and not stale:
            st.write(f"**Reason:** {status['reason']}")
            c1, c2, c3 = st.columns(3)
            c1.metric("Evidence score", f"{status['evidence_score']:.2f}")
            c2.metric("In state (s)", status["state_elapsed_s"])
            c3.metric("Camera", "OK" if status["camera_ok"] else "LOST")
            if st.button("Acknowledge", type="primary", disabled=not status["awaiting_ack"], use_container_width=True):
                request_ack(RUNTIME, MQTT_HOST)
                st.toast("Acknowledged")
        else:
            st.button("Acknowledge", disabled=True, use_container_width=True)
    st.subheader("Incidents")
    rows = IncidentLogger(INCIDENTS).read_all()[-20:][::-1]
    if rows:
        st.dataframe([{"time (UTC)": r.get("ts_iso"), "event": r.get("event"),
                       "state": r.get("state") or "-",
                       "reason": r.get("reason") or ("operator " + r["operator_action"] if r.get("operator_action") else "-"),
                       "score": r.get("evidence_score"), "incident": r.get("incident_id")}
                      for r in rows], use_container_width=True, hide_index=True)
    else:
        st.caption("No incidents logged.")


live()
