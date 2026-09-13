"""Tests for wowtalents.icons (pure matching helpers of stage 9).

Synthetic icons: random smooth patterns as 36 px references; a "review crop" is built
the way the game renders a talent cell: the icon inset by 4 px inside a dark rounded
border, either darkened/desaturated (locked) or full colour with a green border and
a rank digit in the corner (available). Run: cd pipeline && uv run pytest -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFilter

PIPELINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PIPELINE / "src"))

from wowtalents import icons as I  # noqa: E402


# ----------------------------------------------------------------------------- fixtures

def make_icon(seed: int) -> Image.Image:
    rng = np.random.default_rng(seed)
    a = rng.integers(0, 255, size=(6, 6, 3), dtype=np.uint8)
    return Image.fromarray(a).resize((36, 36), Image.BICUBIC).filter(ImageFilter.GaussianBlur(0.6))


def make_crop(icon: Image.Image, *, locked: bool, inset: int = 4, noise: float = 6.0, seed: int = 0) -> Image.Image:
    """Cell as the stream shows it: icon shrunk into a 36 px frame, border, darkening or green ring + digit."""
    rng = np.random.default_rng(seed)
    inner = icon.resize((36 - 2 * inset, 36 - 2 * inset), Image.BILINEAR)
    cell = Image.new("RGB", (36, 36), (30, 28, 24))
    cell.paste(inner, (inset, inset))
    a = np.asarray(cell, dtype=np.float32)
    if locked:
        grey = a.mean(axis=2, keepdims=True)
        a = 0.25 * grey + 0.15 * a  # dark, nearly desaturated
    a = np.clip(a + rng.normal(0, noise, a.shape), 0, 255).astype(np.uint8)
    out = Image.fromarray(a)
    d = ImageDraw.Draw(out)
    if not locked:
        d.rounded_rectangle((0, 0, 35, 35), radius=5, outline=(40, 200, 40), width=2)
        d.rectangle((25, 25, 34, 34), fill=(0, 0, 0))
        d.text((27, 23), "0", fill=(60, 220, 60))
    else:
        d.rounded_rectangle((0, 0, 35, 35), radius=5, outline=(45, 40, 32), width=2)
    return out


@pytest.fixture(scope="module")
def ref_dir(tmp_path_factory) -> Path:
    d = tmp_path_factory.mktemp("ref")
    for i in range(60):
        make_icon(i).save(d / f"icon_{i:02d}.jpg", quality=90)
    (d / "broken.jpg").write_bytes(b"not a jpeg")
    return d


@pytest.fixture(scope="module")
def ref(ref_dir: Path) -> I.Reference:
    return I.load_reference(ref_dir, {f"icon_{i:02d}": ("prior" if i < 10 else "classic-era-client") for i in range(60)})


# ----------------------------------------------------------------------------- features

def test_load_reference_skips_unreadable_and_builds_matrices(ref):
    assert len(ref) == 60 and "broken" not in ref.names
    assert len(ref.feats) == len(I.REF_INSETS)
    assert ref.feats[0].shape == (60, int(I.digit_mask().sum()))
    assert ref.tiers["icon_03"] == "prior" and ref.tiers["icon_42"] == "classic-era-client"
    assert len(ref.phash) == 60


def test_normalise_is_zero_mean_unit_var_and_masks_digit_corner():
    a = np.arange(I.SIZE * I.SIZE, dtype=np.float32).reshape(I.SIZE, I.SIZE)
    v = I.normalise(a, I.digit_mask())
    assert v.ndim == 1 and len(v) == int(I.digit_mask().sum()) < I.SIZE * I.SIZE
    assert abs(v.mean()) < 1e-4 and abs(v.std() - 1) < 1e-3
    assert I.ncc(v, v) == pytest.approx(1.0, abs=1e-3)


def test_is_available_detects_green_border():
    icon = make_icon(1)
    assert I.is_available(make_crop(icon, locked=False))
    assert not I.is_available(make_crop(icon, locked=True))


def test_load_list_parses_tsv(tmp_path):
    p = tmp_path / "reference.tsv"
    p.write_text("# comment\nability_x\tprior\ninv_y\tlater-talents\nBad Name\tprior\ninv_y\tclassic-era-client\n\n")
    assert I.load_list(p) == {"ability_x": "prior", "inv_y": "later-talents"}


# ----------------------------------------------------------------------------- matching

@pytest.mark.parametrize("locked", [True, False])
def test_match_finds_the_right_icon(ref, locked):
    for idx in (0, 17, 59):
        crop = make_crop(make_icon(idx), locked=locked, seed=idx)
        m, sc = I.match_crop(crop, ref)
        assert m is not None, f"icon_{idx:02d} {'locked' if locked else 'available'} not matched"
        assert m["icon"] == f"icon_{idx:02d}"
        assert m["method"] == "visual" and m["score"] >= I.Thresholds().accept_score
        assert m["tier"] == ref.tiers[m["icon"]]
        assert sc.available is (not locked)


def test_unknown_icon_keeps_the_crop(ref):
    crop = make_crop(make_icon(9999), locked=True)
    m, sc = I.match_crop(crop, ref)
    assert m is None
    assert len(sc.top(3)) == 3


def test_prior_hint_wins_when_visually_close(ref):
    crop = make_crop(make_icon(5), locked=True, noise=12.0)
    sc = I.score_crop(crop, ref)
    m = I.decide(sc, ref, prior_icon="icon_05")
    assert m is not None and m["icon"] == "icon_05" and m["method"] == "classic-prior"
    assert m["confidence"] in ("high", "medium")


def test_prior_hint_is_ignored_when_it_disagrees_visually(ref):
    crop = make_crop(make_icon(7), locked=False)
    sc = I.score_crop(crop, ref)
    m = I.decide(sc, ref, prior_icon="icon_40")     # a different, unrelated icon
    assert m is not None and m["icon"] == "icon_07" and m["method"] == "visual"
    # an unknown prior name never crashes the decision
    assert I.decide(sc, ref, prior_icon="not_in_set")["icon"] == "icon_07"


def test_runner_up_skips_near_duplicate_variants(ref_dir, ref):
    # a recoloured copy of icon_11 in the set must not veto icon_11 through the margin rule
    d = ref_dir.parent / "ref_dup"
    d.mkdir(exist_ok=True)
    for p in ref_dir.glob("icon_*.jpg"):
        (d / p.name).write_bytes(p.read_bytes())
    Image.open(ref_dir / "icon_11.jpg").convert("RGB").point(lambda v: min(255, int(v * 1.15))).save(d / "icon_11_v2.jpg", quality=90)
    ref2 = I.load_reference(d)
    crop = make_crop(make_icon(11), locked=True)
    sc = I.score_crop(crop, ref2)
    i, j = ref2.index("icon_11"), ref2.index("icon_11_v2")
    assert I.ref_similarity(ref2, i, j) >= I.Thresholds().duplicate_ncc
    assert sc.scores[i] - sc.scores[j] < I.Thresholds().accept_margin
    m = I.decide(sc, ref2)
    assert m is not None and m["icon"] in ("icon_11", "icon_11_v2") and m["margin"] >= I.Thresholds().accept_margin


def test_visual_winner_contradicting_the_prior_needs_a_clear_lead(ref):
    crop = make_crop(make_icon(7), locked=True, noise=14.0)
    sc = I.score_crop(crop, ref)
    assert I.decide(sc, ref)["icon"] == "icon_07"
    # the prior names another icon in the set: the visual winner must clear the stricter bar
    strict = I.Thresholds(disagree_score=0.99, disagree_margin=0.99)
    assert I.decide(sc, ref, prior_icon="icon_40", th=strict) is None
    lax = I.Thresholds(disagree_score=0.0, disagree_margin=0.0)
    assert I.decide(sc, ref, prior_icon="icon_40", th=lax)["icon"] == "icon_07"


def test_thresholds_can_reject_everything(ref):
    crop = make_crop(make_icon(3), locked=True)
    sc = I.score_crop(crop, ref)
    assert I.decide(sc, ref, th=I.Thresholds(accept_score=1.01, prior_score=1.01)) is None


def test_prior_icons_lookup():
    doc = {"classes": {"paladin": {"trees": [{"talents": [{"name": "Holy Shock ", "icon": "Spell_Holy_SearingLight"}]}]}}}
    assert I.prior_icons(doc, "paladin") == {"holy shock": "spell_holy_searinglight"}
    assert I.prior_icons(doc, "mage") == {}


# ----------------------------------------------------------------------------- apply

def test_apply_matches_updates_every_record_of_the_cell_and_retracts():
    records = [
        {"id": "a", "tree": "Holy", "row": 0, "col": 1, "name": "X"},
        {"id": "b", "tree": "Holy", "row": 0, "col": 1, "name": "X"},         # duplicate hover of the same cell
        {"id": "c", "tree": "Holy", "row": 1, "col": 0, "name": "Y", "icon": "old_icon", "icon_source": "classic",
         "icon_match": {"score": 0.9}},
        {"id": "d", "tree": "Protection", "row": 0, "col": 0, "name": "Z"},
    ]
    matches = {
        "holy/x": {"icon": "spell_holy_x", "score": 0.91, "margin": 0.2, "phash": 6, "method": "visual",
                   "confidence": "high", "tier": "prior", "verified": True, "candidate": {"tree": "Holy", "row": 0, "col": 1}},
        "holy/y": {"icon": None, "candidate": {"tree": "Holy", "row": 1, "col": 0}},
        "protection/gone": {"icon": "inv_gone", "candidate": {"tree": "Protection", "row": 6, "col": 3}},
    }
    n, missing = I.apply_matches(records, matches)
    assert n == 3 and missing == ["protection/gone"]
    for rec in records[:2]:
        assert rec["icon"] == "spell_holy_x" and rec["icon_source"] == "classic"
        assert rec["icon_match"] == {"score": 0.91, "margin": 0.2, "phash": 6, "method": "visual",
                                     "confidence": "high", "tier": "prior", "verified": True}
    assert "icon" not in records[2] and "icon_source" not in records[2] and "icon_match" not in records[2]
    assert "icon" not in records[3]
    # idempotent
    assert I.apply_matches(records, matches)[0] == 0
