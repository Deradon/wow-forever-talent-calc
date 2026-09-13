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
