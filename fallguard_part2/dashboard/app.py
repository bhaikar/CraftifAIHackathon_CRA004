"""FallGuard operator dashboard. Run from the project root."""
from __future__ import annotations
import os, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import streamlit as st
from fg2.incident_log import IncidentLogger
from fg2.runtime_io import read_status, read_latest, request_ack, is_stale, STALE_AFTER_S

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = Path(os.environ.get("FG2_RUNTIME", str(ROOT / "runtime")))
INCIDENTS = Path(os.environ.get("FG2_INCIDENTS", str(RUNTIME / "incidents")))
MQTT_HOST = os.environ.get("FG2_MQTT_HOST") or None

st.set_page_config(page_title="CRAFTIFAI · FallGuard", page_icon="F", layout="wide")
st.markdown("""
<style>
:root { --bg:#11151a; --panel:#1b2128; --line:#303944; --text:#edf2f7; --muted:#9ca8b5; --green:#55c58a; --amber:#e5ad52; --red:#e56b70; --blue:#63b8d6; }
.stApp { background:var(--bg); color:var(--text); }
.block-container { max-width:1400px; padding:2rem 3rem 3rem; }
.panel { background:var(--panel); border:1px solid var(--line); border-radius:14px; padding:1.1rem 1.25rem; margin-bottom:1rem; }
.eyebrow { color:var(--muted); font-size:.74rem; letter-spacing:.12em; text-transform:uppercase; font-weight:700; }
.title { font-size:2rem; font-weight:800; margin:.1rem 0 .2rem; }
.subtle { color:var(--muted); }
.badge { display:inline-block; border:1px solid #596575; border-radius:999px; padding:.32rem .7rem; color:#dce5ed; font-size:.74rem; font-weight:700; letter-spacing:.06em; }
.metric { font-size:1.55rem; font-weight:800; margin-top:.25rem; }
.state { font-size:1.75rem; font-weight:850; text-transform:uppercase; letter-spacing:.02em; }
.good { color:var(--green); } .warn { color:var(--amber); } .bad { color:var(--red); } .info { color:var(--blue); }
[data-testid="stDataFrame"] { border:1px solid var(--line); border-radius:10px; overflow:hidden; }
</style>
""", unsafe_allow_html=True)

COLORS = {"normal":"good", "possible_fall":"warn", "confirmed_fall":"bad", "recovering":"info", "unknown":"warn"}
TEXT = {"normal":"No action required.", "possible_fall":"Check the person and continue evaluating.", "confirmed_fall":"Fall-like event detected. Check on the person.", "recovering":"Recovery detected; review before re-arming.", "unknown":"Detection unavailable; check input health."}

def _incidents():
    try:
        return IncidentLogger(INCIDENTS).read_all()
    except (OSError, ValueError):
        return []

def live():
    status = read_status(RUNTIME)
    stale = is_stale(status, time.time(), STALE_AFTER_S)
    state = (status or {}).get("state", "unknown")
    tone = COLORS.get(state, "warn")
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    h1, h2 = st.columns([3, 2])
    with h1:
        st.markdown('<div class="eyebrow">CRAFTIFAI / FALLGUARD AI</div><div class="title">Assistive fall-state monitoring</div><div class="subtle">Privacy-protected operator view for the synthetic CPU pipeline.</div>', unsafe_allow_html=True)
    with h2:
        st.markdown('<div style="text-align:right"><span class="badge">SIMULATION · CPU MOCK</span><br><span class="subtle">INPUT: %s</span></div>' % ("STALE / UNAVAILABLE" if stale else ("CAMERA OK" if status.get("camera_ok") else "CAMERA LOST")), unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    st.caption("Safety notice: this prototype is assistive and is not a validated medical alarm.")

    if stale:
        st.warning("Pipeline stalled or unavailable. Status is stale — the last state is not current and no preview will be displayed.")
    elif status:
        st.markdown(f'<div class="panel"><div class="eyebrow">CURRENT FALL STATE</div><div class="state {tone}">{state.replace("_", " ")}</div><div class="subtle">{TEXT.get(state, "Input state unavailable.")}</div></div>', unsafe_allow_html=True)
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Evidence", f"{status.get('evidence_score', 0):.2f}")
        c2.metric("State duration", f"{status.get('state_elapsed_s', 0):.1f} s")
        c3.metric("Input health", "OK" if status.get("camera_ok") else "LOST")
        c4.metric("Frame", str(status.get("frame_id", "—")))
        if state == "confirmed_fall":
            st.error("CONFIRMED FALL · Check on the person and acknowledge the event.")
        st.markdown(f'<div class="panel"><b>Classification reason</b><br><span class="subtle">{status.get("reason", "Unavailable")}</span></div>', unsafe_allow_html=True)

    st.markdown('<div class="panel"><div class="eyebrow">PRIVACY-PROTECTED FRAME</div>', unsafe_allow_html=True)
    img = None if stale or not status or not status.get("video_ok") else read_latest(RUNTIME)
    if img:
        st.image(img, caption=f"Blurred output · mode {status.get('blur_mode','unknown')} · updated frame {status.get('frame_id','—')}", width="stretch")
    else:
        st.info("No current image can safely be displayed. Output is withheld when blur, metadata, or freshness cannot be guaranteed.")
    st.markdown('</div>', unsafe_allow_html=True)

    rows = _incidents()
    st.markdown('<div class="panel"><div class="eyebrow">INCIDENT HISTORY</div>', unsafe_allow_html=True)
    if rows:
        events = sorted(rows, key=lambda r: r.get("ts", 0), reverse=True)
        options = ["All"] + sorted({str(r.get("event", "unknown")) for r in events})
        selected = st.selectbox("Filter events", options, label_visibility="collapsed")
        if selected != "All": events = [r for r in events if r.get("event") == selected]
        st.dataframe([{"UTC":r.get("ts_iso","—"), "Event":r.get("event","—"), "State":r.get("state","—"), "Reason":r.get("reason") or ("operator " + r["operator_action"] if r.get("operator_action") else "—"), "Evidence":str(r.get("evidence_score") if r.get("evidence_score") is not None else "—"), "Incident":r.get("incident_id","—")} for r in events], width="stretch", hide_index=True)
    else: st.caption("No incidents logged yet.")
    st.markdown('</div>', unsafe_allow_html=True)

    can_ack = bool(status and not stale and status.get("awaiting_ack"))
    if st.button("Acknowledge current event", type="primary", disabled=not can_ack, width="stretch"):
        request_ack(RUNTIME, MQTT_HOST)
        st.success("Acknowledgement recorded. The upstream state machine must still consume this command before state changes.")

@st.fragment(run_every=1)
def _fragment(): live()
_fragment()
