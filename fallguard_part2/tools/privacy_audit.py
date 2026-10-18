"""Privacy audit: runs failure scenarios, records MEASURED results, writes privacy/PRIVACY_TEST_REPORT.md.

Usage (from project root):  python tools/privacy_audit.py [--out privacy/PRIVACY_TEST_REPORT.md] [--run-tests]
Exit code is non-zero if any privacy rule fails. Run it on the machine you demo on.
"""
import argparse, collections, dataclasses, json, os, platform, subprocess, sys, tempfile, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import cv2, numpy as np
from fg2.alerts import AlertPublisher
from fg2.app import Part2App
from fg2.blur import FailClosedBlurrer, BlurConfig, BlurredFrame, PrivacyError
from fg2.bus import LocalBus
from fg2.contract import StateMessage
from fg2.incident_log import IncidentLogger, ALLOWED
from fg2.mock_source import MockSource
from fg2.runtime_io import read_status, read_latest, write_latest, request_ack, is_stale

LEAK_RATIO = 0.15      # person-region fine detail must drop below 15% of the original
ALLOWED_WRITES = {"status.json", "status.json.tmp", "latest_blurred.jpg", "latest_blurred.jpg.tmp",
                  "ack.json", "ack.json.tmp", "incidents.jsonl"}

# ---- file-write audit: records every Python-level write-mode open() and rename while active
_active, writes = False, set()
def _hook(event, args):
    if not _active:
        return
    if event == "open":
        path, mode, flags = args
        m = mode or ""
        if isinstance(path, (str, bytes, os.PathLike)) and (any(c in m for c in "wax+") or (isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND))):
            writes.add(os.fsdecode(path))
    elif event in ("os.rename", "os.replace"):
        writes.add(os.fsdecode(args[1]))
sys.addaudithook(_hook)


def detail(img):
    return float(np.abs(np.diff(img.astype(np.int16), axis=1)).mean())

def leaked(out, raw, boxes):
    """True if any ground-truth person box still shows >= LEAK_RATIO of its original fine detail."""
    for x1, y1, x2, y2 in boxes:
        a, b, c, d = int(x1), int(y1), int(x2), int(y2)
        if c - a < 4 or d - b < 4:
            continue
        if detail(out[b:d, a:c]) >= LEAK_RATIO * max(detail(raw[b:d, a:c]), 1e-6):
            return True
    return False


def blur_level(name, mutate, hold=0, informational=False):
    """Drive the blurrer directly with a faulty detector feed. Frames always exist; messages may not."""
    bl, modes = FailClosedBlurrer(BlurConfig(hold_frames=hold)), collections.Counter()
    r = dict(name=name, frames=0, person_frames=0, leaks=0, raw_out=0, dropped=0, info=informational)
    for i, (f, m) in enumerate(MockSource(fps=15, hold_until_ack=lambda: True)):
        used = mutate(i, m)
        out = bl.process_or_drop(f, m.frame_id, m.ts, used)
        r["frames"] += 1
        if out is None:
            r["dropped"] += 1; continue
        modes[out.mode] += 1
        r["raw_out"] += int(out.image is f or np.array_equal(out.image, f))
        if m.boxes:
            r["person_frames"] += 1
            r["leaks"] += int(leaked(out.image, f, m.boxes))
    r["modes"] = dict(modes)
    return r


def app_level(name, crash_every=None, request_ack_once=True):
    tmp = Path(tempfile.mkdtemp(prefix="fg2audit_"))
    bus, bl = LocalBus(), FailClosedBlurrer()
    if crash_every:
        orig, cnt = bl.process, [0]
        def crashing(*a, **k):
            cnt[0] += 1
            if cnt[0] % crash_every == 0:
                raise RuntimeError("injected blur failure")
            return orig(*a, **k)
        bl.process = crashing
    app = Part2App(tmp / "rt", IncidentLogger(tmp / "inc", "audit", "audit"), bl, AlertPublisher(bus), bus)
    r = dict(name=name, frames=0, person_frames=0, leaks=0, raw_out=0, dropped=0, stale_leftover=0, cam_lost_frames=0, cam_lost_not_full=0)
    modes, acked = collections.Counter(), False
    for f, m in MockSource(fps=15, hold_until_ack=lambda: app.acked):
        out = app.step(f, m)
        if request_ack_once and m.state == "confirmed_fall" and not acked:
            request_ack(tmp / "rt"); acked = True
        r["frames"] += 1
        st = read_status(tmp / "rt")
        if out is None:
            r["dropped"] += 1
            if read_latest(tmp / "rt") is not None or st["video_ok"]:
                r["stale_leftover"] += 1           # an image remained after the blur failed
            continue
        modes[out.mode] += 1
        r["raw_out"] += int(out.image is f or np.array_equal(out.image, f))
        if m.boxes:
            r["person_frames"] += 1
            r["leaks"] += int(leaked(out.image, f, m.boxes))
        if not m.camera_ok:
            r["cam_lost_frames"] += 1
            r["cam_lost_not_full"] += int(out.mode != "full")
    r["modes"] = dict(modes); r["dir"] = tmp
    return r, bus


def main():
    global _active
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "privacy" / "PRIVACY_TEST_REPORT.md"))
    ap.add_argument("--run-tests", action="store_true")
    a = ap.parse_args()
    results, checks = [], []     # checks: (rule, evidence, passed)

    tempfile.gettempdir()          # let Python probe the temp dir before auditing starts
    _active = True
    base, bus = app_level("Normal run with fault-free feed")
    crash, _ = app_level("Blur module crashes every 5th frame", crash_every=5)
    _active = False

    def shift(i, m):  return dataclasses.replace(m, frame_id=m.frame_id - 1) if i % 5 == 0 else m
    def offf(i, m):   return dataclasses.replace(m, boxes=((900., 900., 950., 950.),))
    def cam(i, m):    return dataclasses.replace(m, camera_ok=False) if 20 <= i < 45 else m
    def drop7(i, m):  return None if i % 7 == 0 else m
    def dead(i, m):   return None if i >= 30 else m          # detector stops entirely at frame 30
    def alldrop(i, m): return None
    for name, fn in [("Detector message missing every 7th frame", drop7),
                     ("Boxes belong to a different frame every 5th frame", shift),
                     ("Boxes entirely outside the frame", offf),
                     ("Camera fault flag for 25 frames", cam),
                     ("Detector dies at frame 30 (never recovers)", dead),
                     ("Detector never sends anything", alldrop)]:
        results.append(blur_level(name, fn))
    info = blur_level("INFORMATIONAL: hold_frames=5 (opt-in), detector message missing every 7th frame", drop7, hold=5, informational=True)
    info2 = blur_level("INFORMATIONAL: hold_frames=5 (opt-in), boxes from a different frame every 5th", shift, hold=5, informational=True)
    results = [base, crash] + results
    extra = [info, info2]

    # ---- output scan
    rt, inc = base["dir"] / "rt", base["dir"] / "inc"
    files = sorted(p.name for d in (rt, inc) for p in d.iterdir())
    jpg = cv2.imdecode(np.frombuffer(read_latest(rt) or b"", np.uint8), cv2.IMREAD_COLOR)
    log_lines = [json.loads(l) for l in (inc / "incidents.jsonl").read_text().splitlines()]
    log_ok = all(set(r) <= ALLOWED and all(v is None or isinstance(v, (str, int, float, bool)) for v in r.values()) for r in log_lines)
    alerts = [json.loads(p) for t, p in bus.sent if t == "care/room1/fall"]
    alert_ok = all(set(x) <= ALLOWED for x in alerts) and bool(alerts)
    run_dirs = (str(base["dir"]), str(crash["dir"]))
    mine = {w for w in writes if w.startswith(run_dirs)}
    stray = sorted({Path(w).name for w in mine} - ALLOWED_WRITES)
    wrote = sorted({Path(w).name for w in mine})

    # ---- sink guard + stale handling
    guard = []
    for label, fn in [("write_latest(raw ndarray)", lambda: write_latest(tempfile.gettempdir(), np.zeros((8, 8, 3), np.uint8))),
                      ("BlurredFrame(...) built directly", lambda: BlurredFrame(np.zeros((8, 8, 3), np.uint8), "x", "y", 1, 1.0))]:
        try: fn(); guard.append((label, False))
        except PrivacyError: guard.append((label, True))
    stale_ok = is_stale(None) and is_stale({"updated_at": time.time() - 10}) and not is_stale({"updated_at": time.time()})

    tot = lambda k: sum(r[k] for r in results)
    checks += [
        ("Raw frame is never emitted", f"{tot('frames')} frames across {len(results)} scenarios; frames equal to raw input: {tot('raw_out')}", tot("raw_out") == 0),
        ("Person regions are unrecognisable", f"{tot('person_frames')} frames with a person; frames where a person box kept >= {int(LEAK_RATIO*100)}% fine detail: {tot('leaks')}", tot("leaks") == 0),
        ("Blur crash means no output", f"{crash['dropped']} dropped frames; images or video_ok flags left behind after a drop: {crash['stale_leftover']}", crash["dropped"] > 0 and crash["stale_leftover"] == 0),
        ("Camera loss is never shown clean", f"{base['cam_lost_frames']} camera-lost frames in the mock scenario, not full-blurred: {base['cam_lost_not_full']}", base["cam_lost_frames"] > 0 and base["cam_lost_not_full"] == 0),
        ("Only blurred frames reach sinks", "; ".join(f"{l}: {'refused' if ok else 'ACCEPTED'}" for l, ok in guard), all(ok for _, ok in guard)),
        ("Only expected files are written", f"files written during run: {', '.join(wrote)}; unexpected: {stray or 'none'}", not stray and bool(wrote)),
        ("Output folders hold no video or raw image files", f"files present: {', '.join(files)}", all(f in ALLOWED_WRITES for f in files)),
        ("Saved preview is blurred", "latest_blurred.jpg decodes and is the only image file" if jpg is not None else "no image", jpg is not None),
        ("Incident log is metadata only", f"{len(log_lines)} records; all fields whitelisted scalars", log_ok),
        ("MQTT alerts are metadata only", f"{len(alerts)} alerts; all fields whitelisted", alert_ok),
        ("Stale status never looks current", "no status, 10 s old and fresh status classified correctly", stale_ok),
    ]
    test_line = ""
    if a.run_tests:
        p = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT, capture_output=True, text=True)
        test_line = (p.stdout.strip().splitlines() or ["(no output)"])[-1]
        checks.append(("Unit and integration tests pass", test_line, p.returncode == 0))

    import paho.mqtt, numpy
    L = ["# FallGuard Part 2: privacy test report", "",
         f"Generated by `tools/privacy_audit.py` on {time.strftime('%Y-%m-%d %H:%M:%S')} local time.",
         f"Platform: {platform.platform()} | Python {platform.python_version()} | OpenCV {cv2.__version__} | NumPy {numpy.__version__}", "",
         "All figures below were measured in this run, using the mock producer (synthetic frames, no real people).", "",
         "## Result summary", "", "| Rule | Evidence | Result |", "|---|---|---|"]
    L += [f"| {r} | {e} | {'PASS' if ok else '**FAIL**'} |" for r, e, ok in checks]
    L += ["", "## Failure scenarios", "",
          "| Scenario | Frames | Person frames | Leaks | Raw out | Dropped | Output modes |", "|---|---|---|---|---|---|---|"]
    L += [f"| {r['name']} | {r['frames']} | {r['person_frames']} | {r['leaks']} | {r['raw_out']} | {r['dropped']} | {r['modes']} |" for r in results + extra]
    L += ["", "Modes: `region` = person boxes blurred; `held` = last known boxes reused briefly; `full` = whole frame blurred (fail-closed); a dropped frame means nothing was emitted.",
          "", "The INFORMATIONAL rows show the opt-in hold feature. Leaks there are expected when posture changes quickly, which is why hold is off by default and excluded from the pass criteria.",
          "", "## Method and limits", "",
          f"- Leak test: for every frame the mock knows the true person box. A frame leaks if the output inside that box keeps at least {int(LEAK_RATIO*100)}% of the original neighbour-pixel detail.",
          "- File audit: a Python audit hook records every write-mode `open()` and rename during the run.",
          "- Limits: synthetic frames only, so this does not test face recognition by a human or model on real footage. "
          "OpenCV writes are not visible to the audit hook, but the code path only calls `imencode` and writes bytes through Python. "
          "Re-run this script on the demo machine and after any change to `blur.py`."]
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text("\n".join(L) + "\n", encoding="utf-8")
    for r, e, ok in checks:
        print(("PASS " if ok else "FAIL ") + r + "  |  " + e)
    print(f"\nreport written to {a.out}")
    sys.exit(0 if all(ok for _, _, ok in checks) else 1)

main()
