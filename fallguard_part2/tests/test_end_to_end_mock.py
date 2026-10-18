import numpy as np
from fg2.blur import FailClosedBlurrer
from fg2.mock_source import MockSource

def detail(img):
    """Mean absolute neighbour difference: high for textured/identifiable content, ~0 once pixelated."""
    a = img.astype(np.int16)
    return float(np.abs(np.diff(a, axis=1)).mean())

def test_every_output_is_blurred_with_fault_injection():
    b, n = FailClosedBlurrer(), 0
    for i, (f, m) in enumerate(MockSource(fps=10)):
        msg = None if i % 7 == 0 else m          # simulate dropped detector messages
        r = b.process_or_drop(f, m.frame_id, m.ts, msg)
        assert r is not None and r.image is not f
        if m.boxes:
            x1, y1, x2, y2 = (int(v) for v in m.boxes[0])
            inner = (slice(y1, y2), slice(x1, x2))
            assert detail(r.image[inner]) < 0.1 * detail(f[inner]), (i, r.mode)
        n += 1
    assert n > 100 and b.errors == 0
