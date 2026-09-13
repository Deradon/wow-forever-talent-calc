"""Icon matching: 36 px talent-cell crops against a reference set of known icons.

Pure helpers for ``stages/09_icons.py``; nothing here touches the network or
the repository (the stage does that). Pipeline:

1. ``load_reference(ref_dir)`` reads ``<name>.jpg`` icons (Wowhead ``medium``
   = 36 px) and precomputes normalised luminance vectors (two trims) and a
   pHash per icon.
2. ``prep_crop(img, inset)`` cuts the cell border off a review crop
   (``data/review/<class>/<tree>/<id>.icon.png``), resizes to ``SIZE`` and
   normalises to zero mean / unit variance with the rank-digit corner masked.
   Locked talents are shown darkened and desaturated, so only structure
   (luminance) is compared and colour is ignored altogether; brightness
   normalisation makes locked and available cells comparable.
3. ``match_crop`` scores the crop against every reference (normalised cross
   correlation, best of two trim pairs), re-ranks the top candidates with a
   pHash distance, and applies a Classic-prior hint (the icon of the
   same-class Classic talent with the same name; a visual winner that
   contradicts the hint needs a clearly stronger score).
4. ``decide`` turns scores into ``{icon, score, margin, method, confidence}``
   or ``None`` (keep the crop).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from PIL import Image, ImageOps

try:  # pHash is a secondary signal; matching works without imagehash
    import imagehash
except ImportError:  # pragma: no cover
    imagehash = None  # type: ignore[assignment]

SIZE = 24                     # comparison resolution (px)
CROP_INSETS = (4, 5)          # cell border of the review crop (36 px cell -> 28/26 px icon)
REF_INSETS = (0, 1)           # paired with CROP_INSETS: reference trim per crop inset
DIGIT_FRAC = 10 / 36          # rank digit box in the bottom-right corner of an available cell
ICON_RE = re.compile(r"^[a-z0-9_-]+$")


@dataclass
class Thresholds:
    accept_score: float = 0.60      # NCC needed for an unaided visual match
    accept_margin: float = 0.04     # best - second best
    strong_score: float = 0.80      # confidence 'high' regardless of margin
    prior_score: float = 0.45       # NCC needed when the Classic prior names the icon
    prior_rank: int = 3             # ... and the prior icon is within the top-N
    phash_max: int = 26             # pHash Hamming distance (of 64) tolerated for an accepted match
    topk: int = 10                  # candidates re-ranked with pHash
    duplicate_ncc: float = 0.90     # two references this similar count as variants of one picture
    disagree_score: float = 0.85    # a visual winner that contradicts the Classic prior needs this NCC ...
    disagree_margin: float = 0.10   # ... and this margin; otherwise the crop is kept for review


@dataclass
class Reference:
    names: list[str]
    tiers: dict[str, str]
    feats: list[np.ndarray]                 # one (N, SIZE*SIZE) matrix per REF_INSETS entry
    phash: list[Any] = field(default_factory=list)   # imagehash.ImageHash per name (or None)

    def __len__(self) -> int:
        return len(self.names)

    def index(self, name: str) -> int | None:
        try:
            return self.names.index(name)
        except ValueError:
            return None


# ----------------------------------------------------------------------------- features

def digit_mask(size: int = SIZE) -> np.ndarray:
    """Boolean mask that hides the rank-digit box (bottom right) of an available cell."""
    m = np.ones((size, size), dtype=bool)
    k = int(size * DIGIT_FRAC) + 1
    m[size - k:, size - k:] = False
    return m


def normalise(a: np.ndarray, mask: np.ndarray | None = None) -> np.ndarray:
    """Zero mean, unit variance over the unmasked pixels; returns a flat float32 vector."""
    a = a.astype(np.float32)
    if mask is not None:
        a = a[mask]
    a = a - a.mean()
    return (a / (a.std() + 1e-6)).ravel()


def _lum(img: Image.Image, inset: int, size: int = SIZE) -> np.ndarray:
    im = img.convert("L")
    w, h = im.size
    if inset:
        im = im.crop((inset, inset, w - inset, h - inset))
    return np.asarray(im.resize((size, size), Image.BILINEAR), dtype=np.float32)


def prep_crop(img: Image.Image, inset: int, size: int = SIZE) -> np.ndarray:
    return normalise(_lum(img, inset, size), digit_mask(size))


def prep_ref(img: Image.Image, inset: int, size: int = SIZE) -> np.ndarray:
    return normalise(_lum(img, inset, size), digit_mask(size))


def ncc(a: np.ndarray, b: np.ndarray) -> float:
    """Normalised cross correlation of two normalised vectors, in [-1, 1]."""
    return float(np.dot(a, b) / len(a))


def phash_of(img: Image.Image, inset: int) -> Any:
    if imagehash is None:
        return None
    im = img.convert("L")
    w, h = im.size
    if inset:
        im = im.crop((inset, inset, w - inset, h - inset))
    return imagehash.phash(ImageOps.autocontrast(im, cutoff=1), hash_size=8)


def is_available(img: Image.Image) -> bool:
    """True when the cell shows the green 'can learn' border (icon in full colour, rank digit shown)."""
    a = np.asarray(img.convert("RGB"), dtype=np.float32)
    ring = np.concatenate([a[0:2].reshape(-1, 3), a[-2:].reshape(-1, 3), a[:, 0:2].reshape(-1, 3), a[:, -2:].reshape(-1, 3)])
    r, g, b = ring.mean(axis=0)
    return bool(g > r + 25 and g > b + 25)


# ----------------------------------------------------------------------------- reference set

def load_reference(ref_dir: Path, tiers: dict[str, str] | None = None, names: Iterable[str] | None = None) -> Reference:
    """Read every ``<name>.jpg`` under ``ref_dir`` (or only ``names``) into a Reference."""
    paths = sorted(ref_dir.glob("*.jpg"))
    if names is not None:
        wanted = set(names)
        paths = [p for p in paths if p.stem in wanted]
    out_names: list[str] = []
    feats: list[list[np.ndarray]] = [[] for _ in REF_INSETS]
    hashes: list[Any] = []
    for p in paths:
        try:
            img = Image.open(p)
            img.load()
        except Exception:  # truncated download etc.
            continue
        if img.size[0] < 16 or img.size[1] < 16:
            continue
        out_names.append(p.stem)
        for i, inset in enumerate(REF_INSETS):
            feats[i].append(prep_ref(img, inset))
        hashes.append(phash_of(img, 0))
    mats = [np.stack(f) if f else np.zeros((0, int(digit_mask().sum())), dtype=np.float32) for f in feats]
    return Reference(out_names, dict(tiers or {}), mats, hashes)


def load_list(path: Path) -> dict[str, str]:
    """``name<TAB>tier`` lines -> {name: tier}; blank lines and ``#`` comments ignored."""
    tiers: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, _, tier = line.partition("\t")
        if ICON_RE.match(name):
            tiers.setdefault(name, tier or "unknown")
    return tiers


# ----------------------------------------------------------------------------- matching

@dataclass
class Scored:
    scores: np.ndarray          # NCC per reference (best over insets)
    order: np.ndarray           # argsort descending
    phash: dict[int, int]       # ref index -> Hamming distance, for the top-k
    available: bool

    def top(self, k: int) -> list[int]:
        return [int(i) for i in self.order[:k]]


def score_crop(img: Image.Image, ref: Reference, th: Thresholds = Thresholds()) -> Scored:
    best = np.full(len(ref), -1.0, dtype=np.float32)
    for ci, ri in zip(CROP_INSETS, range(len(REF_INSETS))):
        c = prep_crop(img, ci)
        s = ref.feats[ri] @ c / len(c)
        np.maximum(best, s, out=best)
    order = np.argsort(-best)
    ph: dict[int, int] = {}
    if imagehash is not None and ref.phash:
        h = phash_of(img, CROP_INSETS[0])
        for i in order[: th.topk]:
            rh = ref.phash[int(i)]
            ph[int(i)] = int(h - rh) if rh is not None else 64
    return Scored(best, order, ph, is_available(img))


def ref_similarity(ref: Reference, i: int, j: int) -> float:
    """NCC between two reference icons (trim 0)."""
    a, b = ref.feats[0][i], ref.feats[0][j]
    return float(np.dot(a, b) / len(a))


def runner_up(sc: Scored, ref: Reference, best_i: int, top: list[int], th: Thresholds) -> float:
    """Score of the first candidate after ``best_i`` that is not a variant of it (-1 if none)."""
    for i in top:
        if i == best_i:
            continue
        if ref_similarity(ref, best_i, i) < th.duplicate_ncc:
            return float(sc.scores[i])
    return -1.0


def decide(sc: Scored, ref: Reference, prior_icon: str | None = None, th: Thresholds = Thresholds()) -> dict | None:
    """Pick the icon for a scored crop; None means 'keep the crop'.

    Returns {icon, score, margin, phash, rank, method, confidence, tier}. ``method`` is
    ``classic-prior`` when the Classic talent of the same name supplied the icon and the
    visual score agrees, ``visual`` when the image alone decided. ``confidence`` is
    ``high`` / ``medium``.
    """
    if len(ref) == 0:
        return None
    top = sc.top(max(th.topk, th.prior_rank))
    best_i = top[0]
    best = float(sc.scores[best_i])
    # margin to the best candidate that is not a near-duplicate of the winner (icon sets contain
    # recoloured variants, e.g. spell_holy_heal / spell_holy_heal02; they must not veto each other)
    margin = best - runner_up(sc, ref, best_i, top, th)

    def _out(i: int, method: str, conf: str) -> dict:
        name = ref.names[i]
        return {"icon": name, "score": round(float(sc.scores[i]), 3), "margin": round(margin, 3),
                "phash": sc.phash.get(i), "rank": top.index(i) if i in top else None,
                "method": method, "confidence": conf, "tier": ref.tiers.get(name, "unknown")}

    if prior_icon:
        pi = ref.index(prior_icon)
        if pi is not None:
            rank = top.index(pi) if pi in top else None
            score = float(sc.scores[pi])
            if rank is not None and rank < th.prior_rank and score >= th.prior_score:
                ph = sc.phash.get(pi)
                if ph is None or ph <= th.phash_max or rank == 0:
                    conf = "high" if (rank == 0 or score >= th.strong_score) else "medium"
                    return _out(pi, "classic-prior", conf)

    ph = sc.phash.get(best_i)
    if prior_icon and ref.index(prior_icon) is not None and ref.names[best_i] != prior_icon:
        # the Classic talent of the same name has a different icon: either Forever changed it (then the
        # visual match is unambiguous) or the crop is noisy (then the prior should not be overruled)
        if best < th.disagree_score or margin < th.disagree_margin:
            return None
    if best >= th.accept_score and (margin >= th.accept_margin or best >= th.strong_score):
        if ph is not None and ph > th.phash_max and best < th.strong_score:
            return None
        conf = "high" if best >= th.strong_score and margin >= th.accept_margin else "medium"
        return _out(best_i, "visual", conf)
    return None


def match_crop(img: Image.Image, ref: Reference, prior_icon: str | None = None,
               th: Thresholds = Thresholds()) -> tuple[dict | None, Scored]:
    sc = score_crop(img, ref, th)
    return decide(sc, ref, prior_icon, th), sc


# ----------------------------------------------------------------------------- prior hint

def prior_icons(prior_doc: dict, cls: str) -> dict[str, str]:
    """{lower-case talent name: icon} for one class of data/prior/classic-era/talents.json."""
    out: dict[str, str] = {}
    for tree in (prior_doc.get("classes", {}).get(cls) or {}).get("trees", []):
        for t in tree.get("talents", []):
            out.setdefault(t["name"].strip().lower(), t["icon"].lower())
    return out


# ----------------------------------------------------------------------------- apply to candidates

def apply_matches(candidates: list[dict], matches: dict[str, dict], *, source: str = "classic") -> tuple[int, list[str]]:
    """Write ``icon`` / ``icon_source`` / ``icon_match`` into candidate records.

    ``matches`` maps ``"<tree>/<talent-id>"`` to the match record written by the stage
    (``candidate: {tree, row, col}``, ``icon``, ...). Every candidate record with the same
    (tree name, row, col) is updated so the record chosen by ``export.dedupe`` carries the
    icon. Records without an accepted match lose a previously applied icon (a re-run after
    a threshold change must be able to retract). Returns (updated records, unmatched keys).
    """
    by_cell: dict[tuple[str, int, int], dict] = {}
    for key, m in matches.items():
        cand = m.get("candidate") or {}
        if m.get("icon") and cand:
            by_cell[(str(cand["tree"]), int(cand["row"]), int(cand["col"]))] = m
    seen: set[tuple[str, int, int]] = set()
    n = 0
    for rec in candidates:
        cell = (str(rec.get("tree") or ""), int(rec.get("row", -1)), int(rec.get("col", -1)))
        m = by_cell.get(cell)
        if m is None:
            had = [rec.pop(k, None) for k in ("icon", "icon_source", "icon_match")]
            if any(v is not None for v in had):
                n += 1
            continue
        seen.add(cell)
        new = {"icon": m["icon"], "icon_source": source,
               "icon_match": {k: m[k] for k in ("score", "margin", "phash", "method", "confidence", "tier", "verified") if k in m}}
        if any(rec.get(k) != v for k, v in new.items()):
            rec.update(new)
            n += 1
    missing = [k for k, m in matches.items() if m.get("icon") and m.get("candidate")
               and (str(m["candidate"]["tree"]), int(m["candidate"]["row"]), int(m["candidate"]["col"])) not in seen]
    return n, missing


def dumps(doc: Any) -> str:
    return json.dumps(doc, ensure_ascii=False, indent=1) + "\n"
