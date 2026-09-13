import pytest
import numpy as np

from wowtalents import ui


def _cells():
    cells = []
    for tree, xs in ui.PRIOR_COLS.items():
        for r, y in enumerate(ui.PRIOR_ROWS, 1):
            for c, x in enumerate(xs, 1):
                cells.append(ui.Cell(tree, r, c, x, y, 36, 36))
    return cells


def _obs(t, h, cell=(2, 5, 3), sharp=1.0):
    return ui.Observation(t=t, sq=int(t), offset=0, bbox=(1002, 330, 227, 124),
                          hash=h, sharpness=sharp, cell_key=cell, payload=f"crop{t}")


def test_segment_id_and_lookup():
    segs = [{"class": "paladin", "t_start": 13640}, {"class": "mage", "t_start": 14760}]
    assert ui.segment_id(segs[0], 1) == "01-paladin-13640"
    assert ui.find_segment(segs, "2")[0] == 2
    assert ui.find_segment(segs, "01-paladin-13640")[1]["class"] == "paladin"
    assert ui.find_segment(segs, "14760")[0] == 2


def test_cell_for_tooltip_reckoning_corner():
    # Reckoning tooltip from the probe handover: x 1003-1225, y 335-452; cell centre (984, 472).
    cell, dist, method = ui.cell_for_tooltip(_cells(), (1003, 335, 222, 117))
    assert (cell.tree, cell.row, cell.col) == (2, 5, 3)
    assert method == "corner" and dist < 5


def test_cell_for_tooltip_clamped_box_falls_back_to_column():
    # A tall tooltip on row 1 gets pushed down by the game: bottom no longer at the cell top,
    # but the left edge still sits on the cell's right edge.
    cells = _cells()
    cell, _, method = ui.cell_for_tooltip(cells, (1002, 100, 225, 260))   # bottom at 360 -> nearest row top 346 (row 3)
    assert method == "corner" and (cell.tree, cell.row, cell.col) == (2, 3, 3)
    far = ui.cell_for_tooltip(cells, (1002, 100, 225, 210))                # bottom at 310: 18 px from row 2 top, still corner
    assert far[2] == "corner" and far[0].row == 2
    none, _, method = ui.cell_for_tooltip(cells, (1700, 100, 225, 100))
    assert none is None and method == "none"


def test_corner_rule_cannot_reach_a_neighbouring_cell():
    """The audit's geometric argument, pinned.

    The owner suspected that a "moved" verdict for priest Blackout came from the
    attribution landing on the cell next door. It cannot: at the real grid pitch the
    top-right corners of two neighbouring cells are 52-56 px apart, `max_dist` is 40, and
    the accepted hovers of all 28 segments matched within 6.7 px at the 99th percentile.
    See docs/handover/2026-09-13-cell-attribution-audit.md.
    """
    cells = _cells()
    gaps = []
    for tree, xs in ui.PRIOR_COLS.items():
        gaps += [b - a for a, b in zip(xs, xs[1:])]
    gaps += [b - a for a, b in zip(ui.PRIOR_ROWS, ui.PRIOR_ROWS[1:])]
    assert min(gaps) > ui.nearest_cell.__defaults__[0]          # every neighbour is past max_dist

    target = next(c for c in cells if (c.tree, c.row, c.col) == (2, 3, 2))
    x, y = target.top_right
    for dx, dy in [(0, 0), (5, 0), (0, 5), (-5, 0), (0, -5), (4, 4)]:
        cell, dist, method = ui.cell_for_tooltip(cells, (x + dx, y + dy - 120, 220, 120))
        assert method == "corner" and (cell.tree, cell.row, cell.col) == (2, 3, 2)
        assert dist <= 8                                         # CORNER_STRICT in stage 4
    # only a gross offset reaches the neighbour, and then the distance is far past
    # CORNER_STRICT, which is exactly where stage 4 asks the cursor before it believes it
    east = next(c for c in cells if (c.tree, c.row, c.col) == (2, 3, 3))
    cell, dist, _ = ui.cell_for_tooltip(cells, (east.top_right[0], east.top_right[1] - 120, 220, 120))
    assert (cell.tree, cell.row, cell.col) == (2, 3, 3) and dist < 1


def test_nearest_cell_prefers_x_alignment_on_ties():
    cells = [ui.Cell(1, 1, 1, 100, 100, 36, 36), ui.Cell(1, 1, 2, 110, 110, 36, 36)]
    # point equidistant (10 px) from both top-right corners: (136,100) and (146,110)
    cell, _ = ui.nearest_cell(cells, (136, 110))
    assert (cell.row, cell.col) == (1, 1)


def test_cell_at_point_margin():
    cells = _cells()
    assert ui.cell_at_point(cells, (984, 472)).col == 3
    assert ui.cell_at_point(cells, (984, 472 + 30)) is None   # gap between rows
    assert ui.cell_at_point(cells, (966 - 4, 460)) is not None


def test_dhash_and_hamming():
    a = np.zeros((50, 100), np.uint8)
    a[:, 50:] = 255
    b = a.copy()
    b[0:2, 0:5] = 255
    ha, hb = ui.dhash(a), ui.dhash(b)
    assert ui.hamming(ha, ha) == 0
    assert ui.hamming(ha, hb) <= 2
    assert ui.hamming(ha, ui.dhash(255 - a)) > 10


def test_group_runs_splits_on_gap_hash_and_cell():
    stream = [
        _obs(1, 0b0000), _obs(2, 0b0001), _obs(3, 0b0011),     # run A (dist 1 each step)
        None,                                                    # gap ends it
        _obs(5, 0b0011), _obs(6, 0b0011),                        # too short (2 frames)
        None,
        _obs(8, 0b0011), _obs(9, 0b0011), _obs(10, 0b1111_0000),  # hash jump splits: 2 + ...
        _obs(11, 0b1111_0000), _obs(12, 0b1111_0000),            # ... 3 -> run B
        _obs(13, 0b1111_0000, cell=(1, 2, 2)), _obs(14, 0b1111_0000, cell=(1, 2, 2)),
        _obs(15, 0b1111_0000, cell=(1, 2, 2)),                   # same hash, other cell -> run C
    ]
    runs = ui.group_runs(stream, max_dist=2, min_len=3)
    assert [len(r) for r in runs] == [3, 3, 3]
    assert [r[0].t for r in runs] == [1, 10, 13]
    assert runs[2][0].cell_key == (1, 2, 2)


def test_run_tracker_keeps_only_sharpest_payload():
    tr = ui.RunTracker(max_dist=2, min_len=2)
    o1, o2, o3 = _obs(1, 0, sharp=1.0), _obs(2, 0, sharp=5.0), _obs(3, 0, sharp=2.0)
    for o in (o1, o2, o3):
        assert tr.push(o) is None
    run = tr.finish()
    assert ui.sharpest(run) is o2 and o2.payload == "crop2"
    assert o1.payload is None and o3.payload is None


def test_trim_bbox_removes_sparse_protrusion():
    mask = np.zeros((100, 100), np.uint8)
    mask[10:60, 20:80] = 255       # solid tooltip
    mask[60:75, 20:24] = 255       # cursor hanging off the bottom-left
    assert ui.trim_bbox(mask, (20, 10, 60, 65)) == (20, 10, 60, 50)


def test_find_tooltip_shape_constraints():
    mask = np.zeros((720, 1920), np.uint8)
    mask[300:420, 1000:1225] = 255   # tooltip-sized box
    mask[500:520, 900:930] = 255     # cursor-sized blob
    mask[100:110, 600:1000] = 255    # long thin line: wrong shape
    bbox, small = ui.find_tooltip(mask)
    assert bbox == (1000, 300, 225, 120)
    assert (900, 500, 30, 20) in small


def test_darkness_separates_tooltips_from_dimmed_grid():
    box = np.full((100, 200, 3), 8, np.uint8)
    box[20:30, 10:150] = 230                     # a line of text
    assert ui.darkness(box) > 0.9
    assert ui.looks_like_tooltip(box)
    dim = np.full((100, 200, 3), 90, np.uint8)   # dimmed icons, no black box
    assert ui.darkness(dim) == 0.0
    assert not ui.looks_like_tooltip(dim)


def test_dark_trim_drops_glued_bright_and_dark_appendages():
    gray = np.full((300, 600), 120, np.uint8)
    gray[100:220, 200:420] = 6                 # tooltip body
    gray[130:135, 210:400] = 220               # a text line (bright)
    gray[100:220, 420:500] = 120               # a dark-ish panel glued on the right: a third of it near-black
    gray[100:220, 420:500][::3] = 30
    gray[60:100, 200:420] = 200                # bright region glued on top
    assert ui.dark_trim(gray, (200, 60, 300, 160)) == (200, 100, 220, 120)
    # nothing near-black: unchanged
    assert ui.dark_trim(np.full((50, 50), 200, np.uint8), (0, 0, 50, 50)) == (0, 0, 50, 50)


def test_find_tooltip_accepts_sparse_outline_over_dark_panel():
    # over a dark panel only the grey border and the text differ from the median: the
    # component covers a tooltip-sized box but has few pixels; it must still be a candidate
    mask = np.zeros((720, 1920), np.uint8)
    mask[300, 1000:1225] = 255
    mask[419, 1000:1225] = 255
    mask[300:420, 1000] = 255
    mask[300:420, 1224] = 255
    for yy in range(320, 400, 14):
        mask[yy:yy + 3, 1010:1180] = 255          # text lines
    gray = np.full((720, 1920), 24, np.uint8)
    gray[300:420, 1000:1225] = 4
    bbox, _ = ui.find_tooltip(mask, gray=gray)
    assert bbox == (1000, 300, 225, 120)


def test_find_tooltip_dark_trim_rescues_wide_blob():
    mask = np.zeros((720, 1920), np.uint8)
    mask[300:420, 1000:1320] = 255            # tooltip + a 95 px appendage on the right (320 wide: over the ceiling)
    gray = np.full((720, 1920), 140, np.uint8)
    gray[300:420, 1000:1225] = 5
    rejected, reasons = [], []
    assert ui.find_tooltip(mask, rejected=rejected, reasons=reasons)[0] is None and reasons == ["wide"]
    assert ui.find_tooltip(mask, gray=gray)[0] == (1000, 300, 225, 120)


def _ghost_frames(n_tooltip: int, n_free: int, box=(300, 200, 220, 120)):
    rng = np.random.default_rng(0)
    base = rng.integers(60, 200, (500, 800, 3), dtype=np.uint8)
    x, y, w, h = box
    frames = []
    for k in range(n_tooltip + n_free):
        f = base.copy()
        if k < n_tooltip:
            f[y:y + h, x:x + w] = 5
            f[y + 20:y + 26, x + 10:x + 150] = 230
        frames.append(f)
    return base, frames


def test_ghost_repair_restores_background_behind_a_long_hover():
    base, frames = _ghost_frames(20, 10)
    bg = np.median(np.stack(frames), axis=0).astype(np.uint8)
    assert ui.darkness(bg[200:320, 300:520]) > 0.9            # the tooltip won the median
    fixed, boxes = ui.repair_ghosts(bg, frames)
    assert len(boxes) == 1
    bx, by, bw, bh = boxes[0]["bbox"]
    assert abs(bx - 300) <= 4 and abs(by - 200) <= 4 and abs(bw - 220) <= 8 and abs(bh - 120) <= 8
    assert len(boxes[0]["tooltip_frames"]) == 20 and len(boxes[0]["free_frames"]) == 10
    assert np.abs(fixed[200:320, 300:520].astype(int) - base[200:320, 300:520].astype(int)).max() <= 1
    assert boxes[0]["darkness_after"] < 0.05 and boxes[0]["repaired"]


def test_ghost_repair_leaves_a_clean_median_alone():
    base, frames = _ghost_frames(3, 27)
    bg = np.median(np.stack(frames), axis=0).astype(np.uint8)
    fixed, boxes = ui.repair_ghosts(bg, frames)
    # three tooltip frames of thirty: the box is unstable but the median there is the clean
    # background (not dark), so no ghost is reported and nothing changes
    assert boxes == [] and np.array_equal(fixed, bg)


def test_ghost_repair_skips_dark_panels():
    # a region that is near-black in the median and in most frames but never a tooltip: the
    # "repair" would not lower the darkness and is discarded
    rng = np.random.default_rng(1)
    base = rng.integers(60, 200, (400, 600, 3), dtype=np.uint8)
    base[100:250, 100:340] = 25                                  # dark panel (dark, but not tooltip-black)
    frames = []
    for k in range(20):
        f = base.copy()
        if k % 4 == 0:
            f[100:250, 100:340] = rng.integers(18, 70, (150, 240, 3), dtype=np.uint8)  # panel texture flickers in 5 frames
        frames.append(f)
    bg = np.median(np.stack(frames), axis=0).astype(np.uint8)
    fixed, boxes = ui.repair_ghosts(bg, frames)
    assert np.array_equal(fixed, bg)
    assert all(b["repaired"] is False for b in boxes)             # a dark panel is not a black box


def test_ghost_repair_from_a_donor_when_every_frame_shows_a_tooltip():
    # the streamer read tooltips over this spot in every sampled frame (the ghost itself in
    # 20, a different tooltip with the same anchor in 10): no in-segment source, but another
    # segment's median of the same class is clean there
    base, frames = _ghost_frames(20, 10)
    for f in frames[20:]:
        f[200:320, 300:520] = 5
        f[260:266, 310:500] = 230
    bg = np.median(np.stack(frames), axis=0).astype(np.uint8)
    donor = base.copy()
    assert ui.repair_ghosts(bg, frames)[1] == []                  # no frame ever differs there: invisible without a donor
    fixed, boxes = ui.repair_ghosts(bg, frames, [donor], (0, 0, 800, 500))
    assert len(boxes) == 1 and boxes[0]["repaired"] == "donor" and boxes[0]["source"] == "donor0"
    x, y, w, h = boxes[0]["bbox"]
    assert np.array_equal(fixed[y:y + h, x:x + w], base[y:y + h, x:x + w])
    # a donor whose window differs elsewhere (other page, points spent, a dialog) is refused
    other = donor.copy()
    other[400:500, :] = 0
    assert ui.repair_ghosts(bg, frames, [other], (0, 0, 800, 500))[1][0]["repaired"] is False


# --------------------------------------------------------------------------- decode_frames

def test_decode_frames_raises_on_a_non_zero_ffmpeg_exit():
    """Silence here is what let stage 4 write a hovers file with zero hovers and exit 0."""
    with pytest.raises(ui.DecodeError) as e:
        list(ui.decode_frames(b"not a video fragment at all", width=16, height=16))
    assert "ffmpeg exited" in str(e.value)


def test_decode_frames_yields_frames_and_exits_cleanly_on_real_video():
    import subprocess
    cmd = ["ffmpeg", "-v", "error", "-nostdin", "-f", "lavfi", "-i", "testsrc=size=16x16:rate=5:duration=1",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-f", "mp4", "-movflags", "frag_keyframe+empty_moov", "pipe:1"]
    data = subprocess.run(cmd, capture_output=True).stdout
    if not data:
        pytest.skip("ffmpeg cannot produce an in-memory fragment here")
    frames = list(ui.decode_frames(data, width=16, height=16))
    assert len(frames) == 5
    assert [off for off, _ in frames] == [0, 1, 2, 3, 4]
    assert frames[0][1].shape == (16, 16, 3)
    every2 = list(ui.decode_frames(data, every=2, width=16, height=16))
    assert [off for off, _ in every2] == [0, 2, 4]
