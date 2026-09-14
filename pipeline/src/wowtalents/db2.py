"""DB2 (wago.tools CSV) import: download, join, render spell text, emit class files.

Stage 10 (``pipeline/stages/10_import_db2.py``) is the CLI; everything reusable
lives here so the tests can exercise it on small CSV fixtures.

Source: ``https://wago.tools/db2/<Table>/csv?build=<build>``. Column names were
verified on Classic Era ``1.15.9.69722`` (docs/briefs/data-prior-and-review.md
section (e)); the loaders read columns **by name**, so an added or reordered
column in a Forever build does not break the join.

The join chain (docs/DATA-SCHEMA.md section 9)::

    TalentTab  ---ID--->  Talent.TabID
    Talent.SpellRank_0..8 ---> SpellName.ID        (talent name, rank count)
                          ---> Spell.ID            (per-rank description template)
                          ---> SpellEffect.SpellID (the numbers the template asks for)
                          ---> SpellMisc.SpellID   -> SpellIconFileDataID
                                                   -> ManifestInterfaceData.ID -> icon name

Politeness: downloads are sequential, cached under ``pipeline/work/db2/<build>/``
and never re-fetched unless ``--force`` is given. One HTTP error stops the run.
"""

from __future__ import annotations

import ast
import csv
import datetime as dt
import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator

from . import fsio
from .text import clean_text, slug

PIPELINE_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = PIPELINE_DIR.parent
WORK_DB2 = PIPELINE_DIR / "work" / "db2"

CSV_URL = "https://wago.tools/db2/{table}/csv?build={build}"
BUILDS_URL = "https://wago.tools/api/builds"
USER_AGENT = "wow4ever-talents/0.1 (+https://github.com/deradon/wow-forever-talent-calc) python-requests"

#: Tables the importer needs, in download order (small ones first so a typo fails fast).
TABLES: tuple[str, ...] = (
    "TalentTab",
    "Talent",
    "SpellName",
    "SpellDuration",
    "SpellRadius",
    "SpellAuraOptions",
    "SpellMisc",
    "ManifestInterfaceData",
    "Spell",
    "SpellEffect",
)

#: Tables whose absence is fatal. The others only feed individual ``$`` formatters
#: (``SpellDuration`` -> ``$d``/``$o1``, ``SpellRadius`` -> ``$a1``,
#: ``SpellAuraOptions`` -> ``$h``/``$n``/``$u``) and degrade to "unsupported".
REQUIRED_TABLES = ("TalentTab", "Talent", "SpellName", "SpellMisc", "ManifestInterfaceData", "Spell", "SpellEffect")
OPTIONAL_TABLES = tuple(t for t in TABLES if t not in REQUIRED_TABLES)

BUILD_RE = re.compile(r"^\d+\.\d+\.\d+\.\d+$")

# Classic ChrClasses.ID -> our class id. Talent.ClassID and the TalentTab.ClassMask
# bit (1 << (ClassID - 1)) both use this numbering.
CLASS_BY_ID: dict[int, str] = {
    1: "warrior", 2: "paladin", 3: "hunter", 4: "rogue", 5: "priest",
    6: "death-knight", 7: "shaman", 8: "mage", 9: "warlock", 10: "monk", 11: "druid",
    12: "demon-hunter", 13: "evoker",
}

DEFAULT_ROWS = 7
DEFAULT_COLS = 4
SCHEMA_VERSION = 1


# ----------------------------------------------------------------------------
# Logging (same shape as export.Log so the stage can print either)
# ----------------------------------------------------------------------------

@dataclass
class Log:
    lines: list[str] = field(default_factory=list)

    def __call__(self, level: str, msg: str) -> None:
        self.lines.append(f"{level} {msg}")

    def error(self, msg: str) -> None:
        self("ERROR", msg)

    def warn(self, msg: str) -> None:
        self("WARN", msg)

    def info(self, msg: str) -> None:
        self("INFO", msg)

    @property
    def errors(self) -> list[str]:
        return [x for x in self.lines if x.startswith("ERROR")]


def now_rfc3339() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


# ----------------------------------------------------------------------------
# fetch
# ----------------------------------------------------------------------------

def build_dir(build: str, root: Path | None = None) -> Path:
    return (root or WORK_DB2) / build


def csv_url(table: str, build: str) -> str:
    return CSV_URL.format(table=table, build=build)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def count_rows(path: Path) -> int:
    """Data rows (header excluded). Quoted newlines are rare in these tables but handled."""
    with path.open("r", encoding="utf-8", newline="") as fh:
        return max(0, sum(1 for _ in csv.reader(fh)) - 1)


def _download(url: str, dest: Path, *, timeout: int = 300) -> None:
    import requests  # local import: the join/render half must import without requests

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with requests.get(url, stream=True, timeout=timeout, headers={"User-Agent": USER_AGENT}) as resp:
        resp.raise_for_status()
        ctype = (resp.headers.get("Content-Type") or "").lower()
        if "html" in ctype:
            raise RuntimeError(f"{url}: server answered with HTML ({ctype}); build or table name wrong?")
        with tmp.open("wb") as fh:
            for chunk in resp.iter_content(1 << 16):
                fh.write(chunk)
    tmp.replace(dest)


def fetch(build: str, *, dest: Path | None = None, tables: Iterable[str] = TABLES, force: bool = False,
          delay: float = 1.5, log: Log | None = None, downloader: Callable[[str, Path], None] | None = None) -> dict:
    """Download the DB2 CSV exports for ``build`` into ``dest`` and write ``manifest.json``.

    Sequential by construction, with ``delay`` seconds between requests. Already
    downloaded tables are kept unless ``force``. Raises on the first HTTP error,
    leaving the manifest unwritten so a partial directory is never mistaken for a
    complete one.
    """
    if not BUILD_RE.match(build):
        raise ValueError(f"build {build!r} is not of the form 1.15.9.69722")
    log = log or Log()
    get = downloader or _download
    out = dest or build_dir(build)
    out.mkdir(parents=True, exist_ok=True)
    entries = []
    for i, table in enumerate(tables):
        path = out / f"{table}.csv"
        url = csv_url(table, build)
        if path.is_file() and not force:
            log.info(f"cached {table}.csv ({path.stat().st_size} bytes)")
        else:
            if i and delay:
                time.sleep(delay)
            log.info(f"GET {url}")
            get(url, path)
        entries.append({
            "table": table, "url": url, "file": path.name,
            "bytes": path.stat().st_size, "rows": count_rows(path), "sha256": sha256_file(path),
        })
    manifest = {
        "build": build,
        "retrievedAt": now_rfc3339(),
        "source": "wago.tools",
        "urlTemplate": CSV_URL,
        "tables": entries,
    }
    fsio.write_json_atomic(out / "manifest.json", manifest)
    return manifest


def read_manifest(build: str, *, dest: Path | None = None) -> dict:
    path = (dest or build_dir(build)) / "manifest.json"
    if not path.is_file():
        raise FileNotFoundError(f"{path} not found; run `10_import_db2.py fetch --build {build}` first")
    return json.loads(path.read_text(encoding="utf-8"))


def verify(build: str, *, dest: Path | None = None, log: Log | None = None) -> bool:
    """Re-hash the cached CSVs against the manifest. False on any mismatch."""
    log = log or Log()
    out = dest or build_dir(build)
    ok = True
    for e in read_manifest(build, dest=out)["tables"]:
        path = out / e["file"]
        if not path.is_file():
            log.error(f"{e['file']}: missing")
            ok = False
        elif sha256_file(path) != e["sha256"]:
            log.error(f"{e['file']}: sha256 mismatch")
            ok = False
    return ok


# ----------------------------------------------------------------------------
# CSV loading
# ----------------------------------------------------------------------------

def iter_csv(path: Path) -> Iterator[dict[str, str]]:
    """Stream a wago CSV as dicts. The tables are large; nothing is kept that a caller did not ask for."""
    with path.open("r", encoding="utf-8", newline="") as fh:
        # some exports carry a BOM
        first = fh.read(1)
        if first != "﻿":
            fh.seek(0)
        yield from csv.DictReader(fh)


def as_int(v: Any, default: int = 0) -> int:
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        try:
            return int(float(str(v).strip()))
        except (TypeError, ValueError):
            return default


def as_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return default


def require_columns(path: Path, row: dict[str, str], columns: Iterable[str]) -> None:
    missing = [c for c in columns if c not in row]
    if missing:
        raise KeyError(f"{path.name}: columns {missing} not in this export (have: {sorted(row)[:12]}...)")


# ----------------------------------------------------------------------------
# Records
# ----------------------------------------------------------------------------

@dataclass
class Effect:
    index: int
    base_points: int = 0
    die_sides: int = 0
    misc_value_0: int = 0
    aura_period: int = 0          # ms
    chain_targets: int = 0
    radius_index: int = 0
    radius: float = 0.0
    real_points_per_level: float = 0.0

    @property
    def value(self) -> int:
        """The number a ``$sN`` token prints, before sign and formatters.

        Brief section (e): ``EffectBasePoints + EffectDieSides`` (Improved Heroic
        Strike: -11 + 1 = -10, then ``$/10;`` -> 1).
        """
        return self.base_points + self.die_sides


@dataclass
class Spell:
    id: int
    name: str = ""
    subtext: str = ""
    description: str = ""
    aura_description: str = ""
    icon_file_data_id: int = 0
    duration_ms: int = 0
    proc_chance: int = 0
    proc_charges: int = 0
    cumulative_aura: int = 0
    effects: dict[int, Effect] = field(default_factory=dict)

    def text(self) -> str:
        return self.description or self.aura_description


@dataclass
class TalentRow:
    id: int
    tab_id: int
    class_id: int
    tier: int
    column: int
    spell_ranks: list[int]
    prereq: list[tuple[int, int]]  # (talent id, PrereqRank as stored)
    flags: int = 0


@dataclass
class TabRow:
    id: int
    name: str
    class_id: int
    order: int
    icon_file_data_id: int
    background: str = ""


@dataclass
class Db2:
    """Everything the join needs, already filtered down to talent spells."""
    build: str
    tabs: dict[int, TabRow] = field(default_factory=dict)
    talents: list[TalentRow] = field(default_factory=list)
    spells: dict[int, Spell] = field(default_factory=dict)
    icons: dict[int, str] = field(default_factory=dict)   # FileDataID -> icon name (no extension)


def _class_from_mask(mask: int) -> int:
    for cid in sorted(CLASS_BY_ID):
        if mask == (1 << (cid - 1)):
            return cid
    # a tab shared by several classes should not happen for talents; take the lowest bit
    return (mask.bit_length()) if mask and (mask & (mask - 1)) == 0 else 0


def load(build: str, *, dest: Path | None = None, log: Log | None = None) -> Db2:
    """Load and join the cached CSVs into a :class:`Db2`.

    The spell tables are read whole rather than filtered to the talent ranks:
    descriptions reference other spells (``$14893s1``, ``$14893d``) that are not
    talent ranks themselves, and a second filtering pass would mean re-reading the
    big CSVs. Classic Era costs ~100 MB of RAM for 31k spells and 40k effects.
    """
    log = log or Log()
    out = dest or build_dir(build)
    for t in REQUIRED_TABLES:
        if not (out / f"{t}.csv").is_file():
            raise FileNotFoundError(f"{out / (t + '.csv')} missing; run `fetch --build {build}` first")
    for t in OPTIONAL_TABLES:
        if not (out / f"{t}.csv").is_file():
            log.warn(f"{t}.csv not downloaded; the formatters it feeds stay unrendered")
    db = Db2(build=build)

    # --- TalentTab -------------------------------------------------------
    p = out / "TalentTab.csv"
    for i, row in enumerate(iter_csv(p)):
        if not i:
            require_columns(p, row, ["ID", "Name_lang", "OrderIndex", "ClassMask", "SpellIconID"])
        mask = as_int(row["ClassMask"])
        cid = _class_from_mask(mask)
        if not cid:
            continue
        db.tabs[as_int(row["ID"])] = TabRow(
            id=as_int(row["ID"]),
            name=clean_text(row["Name_lang"]),
            class_id=cid,
            order=as_int(row["OrderIndex"]),
            icon_file_data_id=as_int(row.get("SpellIconID")),
            background=(row.get("BackgroundFile") or "").strip(),
        )

    # --- Talent ----------------------------------------------------------
    p = out / "Talent.csv"
    wanted_spells: set[int] = set()
    for i, row in enumerate(iter_csv(p)):
        if not i:
            require_columns(p, row, ["ID", "TierID", "ColumnIndex", "TabID", "ClassID", "SpellRank_0"])
        tab = as_int(row["TabID"])
        if tab not in db.tabs:
            continue
        ranks = [as_int(row.get(f"SpellRank_{k}")) for k in range(9)]
        ranks = [s for s in ranks if s > 0]
        if not ranks:
            continue
        prereq = []
        for k in range(3):
            pid = as_int(row.get(f"PrereqTalent_{k}", 0))
            if pid > 0:
                prereq.append((pid, as_int(row.get(f"PrereqRank_{k}", 0))))
        db.talents.append(TalentRow(
            id=as_int(row["ID"]), tab_id=tab, class_id=as_int(row["ClassID"]),
            tier=as_int(row["TierID"]), column=as_int(row["ColumnIndex"]),
            spell_ranks=ranks, prereq=prereq, flags=as_int(row.get("Flags", 0)),
        ))
        wanted_spells.update(ranks)
    log.info(f"{len(db.talents)} talent rows in {len(db.tabs)} tabs, {len(wanted_spells)} rank spell ids")

    def spell(sid: int) -> Spell:
        sp = db.spells.get(sid)
        if sp is None:
            sp = db.spells[sid] = Spell(id=sid)
        return sp

    for sid in wanted_spells:
        spell(sid)

    # --- SpellName -------------------------------------------------------
    p = out / "SpellName.csv"
    for i, row in enumerate(iter_csv(p)):
        if not i:
            require_columns(p, row, ["ID", "Name_lang"])
        spell(as_int(row["ID"])).name = clean_text(row["Name_lang"])

    # --- SpellDuration / SpellRadius (small lookup tables) -----------------
    durations: dict[int, int] = {}
    dp = out / "SpellDuration.csv"
    if dp.is_file():
        for row in iter_csv(dp):
            durations[as_int(row["ID"])] = as_int(row.get("Duration", 0))
    radii: dict[int, float] = {}
    rp = out / "SpellRadius.csv"
    if rp.is_file():
        for row in iter_csv(rp):
            radii[as_int(row["ID"])] = as_float(row.get("Radius", 0))

    # --- SpellAuraOptions ($h proc chance, $n/$u charges) -------------------
    ap = out / "SpellAuraOptions.csv"
    if ap.is_file():
        for i, row in enumerate(iter_csv(ap)):
            if not i:
                require_columns(ap, row, ["SpellID", "ProcChance"])
            if as_int(row.get("DifficultyID", 0)) != 0:
                continue
            sp = spell(as_int(row["SpellID"]))
            sp.proc_chance = as_int(row.get("ProcChance", 0))
            sp.proc_charges = as_int(row.get("ProcCharges", 0))
            sp.cumulative_aura = as_int(row.get("CumulativeAura", 0))

    # --- SpellMisc (icon + duration) ---------------------------------------
    p = out / "SpellMisc.csv"
    for i, row in enumerate(iter_csv(p)):
        if not i:
            require_columns(p, row, ["SpellID", "SpellIconFileDataID"])
        if as_int(row.get("DifficultyID", 0)) != 0:
            continue
        sp = spell(as_int(row["SpellID"]))
        sp.icon_file_data_id = as_int(row["SpellIconFileDataID"])
        sp.duration_ms = durations.get(as_int(row.get("DurationIndex", 0)), 0)

    # --- Spell ------------------------------------------------------------
    p = out / "Spell.csv"
    for i, row in enumerate(iter_csv(p)):
        if not i:
            require_columns(p, row, ["ID", "Description_lang"])
        sp = spell(as_int(row["ID"]))
        sp.subtext = clean_text(row.get("NameSubtext_lang", ""))
        sp.description = (row.get("Description_lang") or "").strip()
        sp.aura_description = (row.get("AuraDescription_lang") or "").strip()

    # --- SpellEffect ------------------------------------------------------
    p = out / "SpellEffect.csv"
    for i, row in enumerate(iter_csv(p)):
        if not i:
            require_columns(p, row, ["SpellID", "EffectIndex", "EffectBasePoints", "EffectDieSides"])
        if as_int(row.get("DifficultyID", 0)) != 0:
            continue
        sp = spell(as_int(row["SpellID"]))
        idx = as_int(row["EffectIndex"])
        ridx = as_int(row.get("EffectRadiusIndex_0", 0))
        sp.effects[idx] = Effect(
            index=idx,
            base_points=as_int(row["EffectBasePoints"]),
            die_sides=as_int(row["EffectDieSides"]),
            misc_value_0=as_int(row.get("EffectMiscValue_0", 0)),
            aura_period=as_int(row.get("EffectAuraPeriod", 0)),
            chain_targets=as_int(row.get("EffectChainTargets", 0)),
            radius_index=ridx,
            radius=radii.get(ridx, 0.0),
            real_points_per_level=as_float(row.get("EffectRealPointsPerLevel", 0)),
        )

    # --- ManifestInterfaceData (icons only) --------------------------------
    p = out / "ManifestInterfaceData.csv"
    for i, row in enumerate(iter_csv(p)):
        if not i:
            require_columns(p, row, ["ID", "FilePath", "FileName"])
        path_ = (row.get("FilePath") or "").replace("/", "\\").lower()
        if "\\icons\\" not in path_:
            continue
        name = (row.get("FileName") or "").strip()
        if not name:
            continue
        db.icons[as_int(row["ID"])] = name.rsplit(".", 1)[0].lower()
    log.info(f"{len(db.spells)} spells, {len(db.icons)} icon file ids")
    return db


# ----------------------------------------------------------------------------
# Spell description templates ($-formatters)
# ----------------------------------------------------------------------------

#: One pass over the string, alternatives tried left to right at each ``$``. The order
#: matters: ``$lsec:secs;`` must win over the plain-token branch, which would otherwise
#: read it as the letter ``l``.
_SUB_RE = re.compile(
    r"""
    (?P<plural>\$(?P<pcap>[lL])(?P<sing>[^:;$]*):(?P<plur>[^;$]*);)
  | (?P<gender>\$(?P<gcap>[gG])(?P<male>[^:;$]*):(?P<female>[^;$]*);)
  | (?P<brace>\$\{[^}]*\})
  | (?P<token>\$
        (?P<ops>(?:[/*]\d+(?:\.\d+)?;)*)    # arithmetic prefix chain, e.g. $/10; $*2;
        (?P<spell>\d+)?                      # cross-spell reference, e.g. $14893d
        (?P<letter>[a-zA-Z])
        (?P<index>\d+)?
    )
    """,
    re.VERBOSE,
)

#: ``$?<condition>[then][else]`` — a client-side conditional (Season of Discovery runes in
#: Classic Era, and whatever Forever uses it for). Matched with a bracket scanner because
#: the branches nest.
_COND_RE = re.compile(r"\$\?\$?(?P<cond>[aAsS]\d+(?:\s*[&|]\s*\$?[aAsS]\d+)*)\s*\[")

#: Letters the renderer understands. Anything else is left verbatim and reported.
SUPPORTED_LETTERS = set("sSmMoOdDtThHaAxXnNuUiIbB")


def _fmt_number(x: float) -> str:
    """WoW prints whole numbers without a decimal point and a short decimal otherwise."""
    if abs(x - round(x)) < 1e-9:
        return str(int(round(x)))
    return f"{round(x, 2):g}"


def _match_bracket(s: str, start: int) -> tuple[str, int] | None:
    """``s[start]`` is ``[``; return the balanced contents and the index after ``]``."""
    depth = 0
    for i in range(start, len(s)):
        if s[i] == "[":
            depth += 1
        elif s[i] == "]":
            depth -= 1
            if depth == 0:
                return s[start + 1:i], i + 1
    return None


@dataclass
class RenderResult:
    text: str
    unsupported: list[str] = field(default_factory=list)   # tokens left verbatim
    conditionals: list[str] = field(default_factory=list)  # $?cond[..][..] resolved to the else branch
    last_value: float | None = None


class Renderer:
    """Renders a spell's ``Description_lang`` into the text the client shows.

    Supported formatters (the handover has the same table with counts):

    =====================  ====================================================
    ``$s1..$s9`` ``$S1``   effect value ``EffectBasePoints + EffectDieSides``,
                           printed as its absolute value ("reduces ... by 10")
    ``$m1`` / ``$M1``      min (``BasePoints + 1``) / max roll of the effect
    ``$o1``                periodic total = value x ticks (duration / aura period)
    ``$t1``                aura period in seconds
    ``$d``                 duration, "30 sec" / "2 min"
    ``$a1``                effect radius (SpellRadius)
    ``$x1``                chain targets        ``$i``  EffectMiscValue_0
    ``$h``                 proc chance          ``$n`` / ``$u``  charges / stacks
    ``$b``                 line break
    ``$<spellid><token>``  the same tokens resolved against another spell
    ``$/N;`` ``$*N;``      divide / multiply the value that follows (chainable)
    ``$lone:many;``        plural, chosen by the last number printed
    ``$ghe:she;``          gender, always rendered male
    ``$?<cond>[a][b]``     conditional: rendered as branch ``b`` (see below)
    =====================  ====================================================

    Not supported, left verbatim and listed in ``RenderResult.unsupported``:
    ``${expr}`` script expressions, and any ``$`` letter outside the table above
    (``$c``, ``$e``, ``$p``, ``$w``, ``$PCT``, ...).

    ``$?<cond>[a][b]`` is rendered as the **else** branch, i.e. as the client shows it
    when the condition does not hold. In Classic Era every such condition is a Season of
    Discovery rune ("does the player know spell 446374"), and the else branch is the
    plain Classic Era wording, which is what we want. It is a guess about the *player*,
    not about the data, so every talent that used one is listed in
    ``RenderResult.conditionals`` and in the build report.
    """

    def __init__(self, spells: dict[int, Spell]):
        self.spells = spells

    # -- individual tokens ------------------------------------------------
    def _effect(self, sp: Spell, index: int) -> Effect | None:
        return sp.effects.get(max(0, index - 1))   # $s1 is EffectIndex 0

    def _token_value(self, sp: Spell, letter: str, index: int) -> float | None:
        low = letter.lower()
        eff = self._effect(sp, index)
        if low == "s":
            return abs(eff.value) if eff else None
        if low == "m":
            if not eff:
                return None
            return abs(eff.base_points + 1) if letter == "m" else abs(eff.base_points + eff.die_sides)
        if low == "o":
            if not eff or not eff.aura_period or not sp.duration_ms:
                return None
            ticks = max(1, round(sp.duration_ms / eff.aura_period))
            return abs(eff.value) * ticks
        if low == "t":
            return eff.aura_period / 1000 if eff and eff.aura_period else None
        if low == "a":
            return eff.radius if eff and eff.radius else None
        if low == "x":
            return eff.chain_targets if eff and eff.chain_targets else None
        if low == "i":
            return eff.misc_value_0 if eff and eff.misc_value_0 else None
        if low == "h":
            return sp.proc_chance or None
        if low == "n":
            return sp.proc_charges or None
        if low == "u":
            return sp.cumulative_aura or None
        return None

    def _token_range(self, sp: Spell, letter: str, index: int) -> tuple[float, float] | None:
        """``$sN`` prints "min to max" when the effect rolls a range (``EffectDieSides > 1``).

        Shield Slam effect 2 is ``BasePoints 224, DieSides 11`` and the client shows
        "225 to 235 damage".
        """
        if letter.lower() != "s":
            return None
        eff = self._effect(sp, index)
        if eff is None or eff.die_sides <= 1:
            return None
        lo, hi = eff.base_points + 1, eff.base_points + eff.die_sides
        return (abs(lo), abs(hi)) if lo <= hi else (abs(hi), abs(lo))

    @staticmethod
    def _apply_ops(val: float, ops: str) -> float:
        for op, n in re.findall(r"([/*])(\d+(?:\.\d+)?);", ops):
            val = val / float(n) if op == "/" else val * float(n)
        return val

    def _duration_seconds(self, sp: Spell) -> float | None:
        return sp.duration_ms / 1000 if sp.duration_ms > 0 else None

    def _duration_text(self, sp: Spell) -> str | None:
        secs = self._duration_seconds(sp)
        if secs is None:
            return None
        if secs >= 60 and abs(secs / 60 - round(secs / 60)) < 1e-9:
            return f"{int(round(secs / 60))} min"
        return f"{_fmt_number(secs)} sec"

    # -- ${...} arithmetic -------------------------------------------------
    def _eval_expr(self, sp: Spell, expr: str) -> float | None:
        """Evaluate a ``${...}`` expression over ``+ - * / ( )`` and the numeric tokens.

        ``${$d-1}`` (Mana Tide Totem) is the only shape Classic Era uses. Anything with a
        token we cannot resolve, or an operator outside the whitelist, returns ``None``
        and the expression is reported as unsupported.
        """
        def num(m: re.Match) -> str:
            target = self.spells.get(as_int(m.group("spell"))) if m.group("spell") else sp
            if target is None:
                raise ValueError(m.group(0))
            letter, index = m.group("letter"), as_int(m.group("index"), 1)
            v = self._duration_seconds(target) if letter in "dD" and not m.group("index") \
                else self._token_value(target, letter, index)
            if v is None:
                raise ValueError(m.group(0))
            return _fmt_number(self._apply_ops(v, m.group("ops") or ""))

        try:
            filled = re.sub(
                r"\$(?P<ops>(?:[/*]\d+(?:\.\d+)?;)*)(?P<spell>\d+)?(?P<letter>[a-zA-Z]+)(?P<index>\d+)?",
                num, expr)
            tree = ast.parse(filled, mode="eval")
        except (ValueError, SyntaxError):
            return None
        allowed = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Add, ast.Sub,
                   ast.Mult, ast.Div, ast.USub, ast.UAdd)
        for node in ast.walk(tree):
            if not isinstance(node, allowed) or (isinstance(node, ast.Constant) and not isinstance(node.value, (int, float))):
                return None
        try:
            return float(eval(compile(tree, "<db2>", "eval"), {"__builtins__": {}}, {}))  # noqa: S307 - whitelisted AST
        except (ArithmeticError, TypeError):
            return None

    # -- whole strings ----------------------------------------------------
    def _resolve_conditionals(self, raw: str, seen: list[str]) -> str:
        out, pos = [], 0
        while True:
            m = _COND_RE.search(raw, pos)
            if not m:
                out.append(raw[pos:])
                return "".join(out)
            first = _match_bracket(raw, m.end() - 1)
            if first is None:
                out.append(raw[pos:m.end()])
                pos = m.end()
                continue
            then_text, after = first
            else_text = ""
            if after < len(raw) and raw[after] == "[":
                second = _match_bracket(raw, after)
                if second is not None:
                    else_text, after = second
            seen.append(raw[m.start():after])
            out.append(raw[pos:m.start()])
            out.append(self._resolve_conditionals(else_text, seen))
            pos = after

    def render(self, spell_id: int, text: str | None = None) -> RenderResult:
        sp = self.spells.get(spell_id)
        if sp is None:
            return RenderResult(text or "", ["<unknown spell>"])
        raw = text if text is not None else sp.text()
        if not raw:
            return RenderResult("")
        unsupported: list[str] = []
        conditionals: list[str] = []
        state: dict[str, float | None] = {"last": None}
        raw = self._resolve_conditionals(raw, conditionals)

        def sub(m: re.Match) -> str:
            if m.group("plural") is not None:
                last = state["last"]
                return m.group("sing") if last is not None and abs(last) == 1 else m.group("plur")
            if m.group("gender") is not None:
                return m.group("male")
            if m.group("brace") is not None:
                whole = m.group("brace")
                v = self._eval_expr(sp, whole[2:-1])
                if v is None:
                    unsupported.append(whole)
                    return whole
                state["last"] = v
                return _fmt_number(v)
            whole = m.group("token")
            letter, index = m.group("letter"), as_int(m.group("index"), 1)
            target = self.spells.get(as_int(m.group("spell"))) if m.group("spell") else sp
            if target is None or letter not in SUPPORTED_LETTERS:
                unsupported.append(whole)
                return whole
            # "$b" is a line break; "$b1" is a token we do not know (Relentless Strikes)
            if letter in "bB" and not m.group("index"):
                return "\n"
            if letter in "dD" and not m.group("index"):
                d = self._duration_text(target)
                if d is None:
                    unsupported.append(whole)
                    return whole
                return d
            ops = m.group("ops") or ""
            rng = self._token_range(target, letter, index)
            if rng is not None:
                lo, hi = (self._apply_ops(v, ops) for v in rng)
                state["last"] = hi
                return f"{_fmt_number(lo)} to {_fmt_number(hi)}"
            val = self._token_value(target, letter, index)
            if val is None:
                unsupported.append(whole)
                return whole
            val = self._apply_ops(val, ops)
            state["last"] = val
            return _fmt_number(val)

        out = _SUB_RE.sub(sub, raw)
        # anything still carrying a $ is a token we do not know. The token regex stops after
        # one letter ("$PCT" matches as "$P"), so a longer leftover replaces its own prefix.
        for m in re.finditer(r"\$\S*", out):
            leftover = m.group(0).rstrip(".,;:%)]")
            if not leftover:
                continue
            shorter = [u for u in unsupported if leftover.startswith(u)]
            if shorter:
                unsupported = [u for u in unsupported if u not in shorter]
                unsupported.append(leftover)
            elif not any(u.startswith(leftover) for u in unsupported):
                unsupported.append(leftover)
        return RenderResult(clean_text(out), sorted(set(unsupported)), sorted(set(conditionals)), state["last"])


# ----------------------------------------------------------------------------
# Template + slots (same rule as data/prior/classic-era/build.py)
# ----------------------------------------------------------------------------

TOKEN_RE = re.compile(r"\d+(?:\.\d+)?|(?<!\d)\.\d+|[A-Za-z]+")
NUM_RE = re.compile(r"^(?:\d+(?:\.\d+)?|\.\d+)$")


def _stem(word: str) -> str:
    return word[:-1] if len(word) > 3 and word.endswith("s") else word


def _skeleton(text: str) -> str:
    return TOKEN_RE.sub("\x00", text)


def _value(s: str) -> float | int | str:
    if NUM_RE.match(s):
        f = float(s)
        return int(f) if f.is_integer() and "." not in s else f
    return s


def template_and_slots(rank_texts: list[str]) -> tuple[str | None, list[list[float | int | str]] | None]:
    """Turn per-rank sentences into ``(description template, slots per rank)``.

    Only tokens that differ between ranks become ``{n}``; a word that differs only by a
    trailing plural ``s`` becomes a ``""``/``"s"`` slot (DATA-SCHEMA.md section 5).
    Returns ``(None, None)`` when the sentence shape changes between ranks — the caller
    then stores the full strings in ``ranks`` (the schema's string form).
    """
    if not rank_texts:
        return None, None
    if len({_skeleton(t) for t in rank_texts}) != 1:
        return None, None
    per_rank = [TOKEN_RE.findall(t) for t in rank_texts]
    if len({len(x) for x in per_rank}) != 1:
        return None, None
    base = rank_texts[0]
    tokens = per_rank[0]
    varying: list[int] = []
    for i in range(len(tokens)):
        col = [p[i] for p in per_rank]
        if len(set(col)) == 1:
            continue
        if all(NUM_RE.match(v) for v in col):
            varying.append(i)
        elif len({_stem(v).lower() for v in col}) == 1 and all(v.lower() in (_stem(v).lower(), _stem(v).lower() + "s") for v in col):
            varying.append(i)   # plural slot
        else:
            return None, None
    if not varying:
        # every rank identical: a single-rank template with no slots
        return base, [[] for _ in rank_texts]

    out: list[str] = []
    pos = 0
    n = 0
    idx = 0
    plural_stem: dict[int, str] = {}
    for m in TOKEN_RE.finditer(base):
        if idx in varying:
            out.append(base[pos:m.start()])
            if not NUM_RE.match(m.group(0)):
                stem = _stem(m.group(0))
                plural_stem[n] = stem
                out.append(stem + "{%d}" % n)
            else:
                out.append("{%d}" % n)
            pos = m.end()
            n += 1
        idx += 1
    out.append(base[pos:])
    template = "".join(out)

    slots: list[list[float | int | str]] = []
    for p in per_rank:
        row: list[float | int | str] = []
        for k, i in enumerate(varying):
            tok = p[i]
            if NUM_RE.match(tok):
                row.append(_value(tok))
            else:
                stem = plural_stem[k]
                row.append(tok[len(stem):])
        slots.append(row)
    return template, slots


def _fill(template: str, slots: list) -> str:
    return re.sub(r"\{(\d+)\}", lambda m: str(slots[int(m.group(1))]), template)


# ----------------------------------------------------------------------------
# DB2 -> class documents (docs/DATA-SCHEMA.md section 4)
# ----------------------------------------------------------------------------

#: Point rules are not in DB2 (no table carries "51 points, 5 per row"), so they come
#: from the Classic prior and stay ``classic-prior`` until someone confirms them in the
#: beta client. Change here if Forever ships different numbers.
RULES_CLASSIC = {"pointsPerRow": 5, "maxPoints": 51, "firstPointLevel": 10, "maxLevel": 60,
                 "rulesSource": "classic-prior"}
PAGES = [{"id": "primary", "name": "Primary"}]
FALLBACK_ICON = "inv_misc_questionmark"


def class_name(cls: str) -> str:
    return " ".join(w.capitalize() for w in cls.split("-"))


def highest_encoding_version(root: Path) -> int:
    enc = root / "data" / "encoding"
    versions = [int(m.group(1)) for p in enc.glob("v*.json") if (m := re.fullmatch(r"v(\d+)\.json", p.name))] if enc.is_dir() else []
    return max(versions) if versions else 1


@dataclass
class TalentBuild:
    """One joined talent, before it becomes a schema record."""
    row: TalentRow
    tab: TabRow
    name: str
    texts: list[str]
    unsupported: list[str]
    conditionals: list[str]
    icon: str | None


def _assign_ids(entries: list[TalentBuild], log: Log) -> dict[int, str]:
    """Slug of the talent name, ``-<treeId>`` appended on a collision (DATA-SCHEMA.md section 3).

    Ids are unique **per class file**, not globally: warrior and paladin may both have a
    ``shield-specialization``. Collisions are therefore resolved inside one class only.
    """
    ids: dict[int, str] = {}
    by_class: dict[int, list[TalentBuild]] = {}
    for e in entries:
        by_class.setdefault(e.tab.class_id, []).append(e)
    for class_id, group in sorted(by_class.items()):
        cls = CLASS_BY_ID.get(class_id, f"class-{class_id}")
        by_slug: dict[str, list[TalentBuild]] = {}
        for e in group:
            by_slug.setdefault(slug(e.name), []).append(e)
        taken: set[str] = set()
        for s, same in sorted(by_slug.items()):
            for e in same:
                cand = s if len(same) == 1 else f"{s}-{slug(e.tab.name)}"
                if len(same) > 1:
                    log.info(f"{cls}: talent id collision on {s!r}: {e.name} ({e.tab.name}) -> {cand}")
                n = 2
                while cand in taken:   # same name twice in one tree: should not happen, but stays unique
                    log.warn(f"{cls}: duplicate talent id {cand!r}; using {cand}-{n}")
                    cand, n = f"{cand}-{n}", n + 1
                taken.add(cand)
                ids[e.row.id] = cand
    return ids


def build_class_docs(db: Db2, *, root: Path = REPO_ROOT, log: Log | None = None,
                     generated_at: str | None = None) -> tuple[dict[str, dict], dict]:
    """Join everything into ``{class id: class document}`` plus an import report."""
    log = log or Log()
    renderer = Renderer(db.spells)
    data_version = highest_encoding_version(root)
    stamp = generated_at or now_rfc3339()

    entries: list[TalentBuild] = []
    for tr in sorted(db.talents, key=lambda t: (t.tab_id, t.tier, t.column)):
        tab = db.tabs[tr.tab_id]
        first = db.spells.get(tr.spell_ranks[0])
        if first is None or not first.name:
            log.warn(f"talent {tr.id}: spell {tr.spell_ranks[0]} has no SpellName row; skipped")
            continue
        texts, unsup, conds = [], [], []
        for sid in tr.spell_ranks:
            res = renderer.render(sid)
            texts.append(res.text)
            unsup.extend(res.unsupported)
            conds.extend(res.conditionals)
        icon_id = first.icon_file_data_id
        icon = db.icons.get(icon_id)
        if icon is None:
            log.warn(f"talent {tr.id} ({first.name}): FileDataID {icon_id} not in ManifestInterfaceData; "
                     f"icon falls back to {FALLBACK_ICON}")
        entries.append(TalentBuild(tr, tab, first.name, texts, sorted(set(unsup)), sorted(set(conds)), icon))

    ids = _assign_ids(entries, log)
    report: dict[str, Any] = {
        "build": db.build, "generatedAt": stamp, "classes": {},
        "unsupportedFormatters": {}, "conditionalTalents": [], "stringFormRanks": [], "missingIcons": [],
    }
    by_class: dict[str, list[TalentBuild]] = {}
    for e in entries:
        by_class.setdefault(CLASS_BY_ID.get(e.tab.class_id, f"class-{e.tab.class_id}"), []).append(e)

    docs: dict[str, dict] = {}
    for cls, group in sorted(by_class.items()):
        tabs = {e.tab.id: e.tab for e in group}
        trees = []
        for tab in sorted(tabs.values(), key=lambda t: (t.order, t.id)):
            mine = [e for e in group if e.tab.id == tab.id]
            talents = []
            for e in mine:
                tid = ids[e.row.id]
                path = f"{cls}/{slug(tab.name)}/{tid}"
                template, slots = template_and_slots(e.texts)
                if template is None:
                    description, ranks = e.texts[0], list(e.texts)
                    report["stringFormRanks"].append(path)
                else:
                    description, ranks = template, slots
                requires = []
                for pid, prank in e.row.prereq:
                    target = ids.get(pid)
                    if target is None:
                        log.warn(f"{path}: prerequisite talent {pid} is not in this import; dropped")
                        continue
                    # PrereqRank is 0-based; +1 equalled the target's maxRank for all 65
                    # Classic Era edges, i.e. a Classic arrow always means "maxed"
                    requires.append({"talent": target, "rank": prank + 1})
                rec: dict[str, Any] = {
                    "id": tid,
                    "name": e.name,
                    "row": e.row.tier,
                    "col": e.row.column,
                    "maxRank": len(e.row.spell_ranks),
                    "icon": e.icon or FALLBACK_ICON,
                    "iconSource": "datamined",
                    "description": description,
                    "ranks": ranks,
                    "ranksObserved": list(range(1, len(e.row.spell_ranks) + 1)),
                    "ranksSource": "observed",
                    "spellIds": list(e.row.spell_ranks),
                    "source": {"kind": "datamined", "build": db.build, "talentId": e.row.id, "reviewed": False},
                }
                if requires:
                    rec["requires"] = requires
                notes = []
                if e.unsupported:
                    notes.append("unrendered formatter(s): " + ", ".join(e.unsupported))
                    for u in e.unsupported:
                        report["unsupportedFormatters"].setdefault(u, []).append(path)
                if e.conditionals:
                    notes.append(f"{len(e.conditionals)} $?cond[..][..] conditional(s) rendered as the else branch")
                    report["conditionalTalents"].append(path)
                if e.icon is None:
                    report["missingIcons"].append(path)
                if notes:
                    rec["source"]["note"] = "; ".join(notes)
                talents.append(rec)
            talents.sort(key=lambda t: (t["row"], t["col"]))
            trees.append({
                "id": slug(tab.name),
                "name": tab.name,
                "page": "primary",
                "order": tab.order,
                "icon": db.icons.get(tab.icon_file_data_id) or FALLBACK_ICON,
                "rows": max(DEFAULT_ROWS, max(t["row"] for t in talents) + 1),
                "cols": max(DEFAULT_COLS, max(t["col"] for t in talents) + 1),
                "datamined": {"talentTabId": tab.id, "build": db.build},
                "talents": talents,
            })
        docs[cls] = {
            "$schema": "../../schema/class.schema.json",
            "schemaVersion": SCHEMA_VERSION,
            "class": cls,
            "className": class_name(cls),
            "dataVersion": data_version,
            "dataSource": "datamined",
            "generatedAt": stamp,
            "rules": dict(RULES_CLASSIC),
            "pages": [dict(p) for p in PAGES],
            "trees": trees,
            "notes": [
                f"Datamined from wago.tools DB2 exports for build {db.build}; "
                "point rules (51/5/10/60) are the Classic prior, not DB2.",
            ],
        }
        report["classes"][cls] = {"trees": len(trees), "talents": sum(len(t["talents"]) for t in trees)}
    report["totals"] = {
        "classes": len(docs),
        "trees": sum(c["trees"] for c in report["classes"].values()),
        "talents": sum(c["talents"] for c in report["classes"].values()),
    }
    return docs, report


def report_markdown(report: dict) -> str:
    t = report["totals"]
    out = [f"# Datamined import {report['build']}", "",
           f"Generated {report['generatedAt']} from wago.tools DB2 exports.", "",
           f"- {t['classes']} classes, {t['trees']} trees, {t['talents']} talents", ""]
    out += ["| class | trees | talents |", "|---|---:|---:|"]
    for cls, c in sorted(report["classes"].items()):
        out.append(f"| {cls} | {c['trees']} | {c['talents']} |")
    out += ["", "## Unrendered formatters", ""]
    if report["unsupportedFormatters"]:
        out += ["| token | talents | where |", "|---|---:|---|"]
        for tok, where in sorted(report["unsupportedFormatters"].items(), key=lambda kv: (-len(kv[1]), kv[0])):
            out.append(f"| `{tok}` | {len(where)} | {', '.join(sorted(set(where))[:4])} |")
    else:
        out.append("None: every `$` token in every rank text rendered.")
    out += ["", "## Conditional text (`$?cond[a][b]`, rendered as the else branch)", ""]
    out += ([f"- {p}" for p in sorted(report["conditionalTalents"])] or ["None."])
    out += ["", "## Ranks stored as full strings (sentence shape changes per rank)", ""]
    out += ([f"- {p}" for p in sorted(report["stringFormRanks"])] or ["None."])
    if report["missingIcons"]:
        out += ["", "## Icons not in ManifestInterfaceData", ""] + [f"- {p}" for p in sorted(report["missingIcons"])]
    return "\n".join(out) + "\n"


# ----------------------------------------------------------------------------
# compare-prior: the renderer's regression check against data/prior/classic-era
# ----------------------------------------------------------------------------

def compare_prior(docs: dict[str, dict], prior: dict) -> dict:
    """Check a Classic Era import against ``data/prior/classic-era/talents.json``.

    The prior was built from Wowhead's Classic talent data and an independent spell dump,
    so it is a genuine second opinion on the join *and* on the ``$``-formatter renderer.
    Talents are matched by ``source.talentId`` == ``classicTalentId``: the prior has the
    same Talent.db2 ids, so a name change between snapshots does not break the pairing.
    """
    by_id: dict[int, tuple[str, str, dict]] = {}
    ptrees = 0
    for cls, cdoc in (prior.get("classes") or {}).items():
        for tree in cdoc.get("trees", []):
            ptrees += 1
            for t in tree.get("talents", []):
                by_id[t["classicTalentId"]] = (cls, tree["id"], t)
    res: dict[str, Any] = {
        "prior": {"trees": ptrees, "talents": len(by_id)},
        "datamined": {"classes": len(docs),
                      "trees": sum(len(d["trees"]) for d in docs.values()),
                      "talents": sum(len(t["talents"]) for d in docs.values() for t in d["trees"])},
        "matched": 0, "unmatched": [], "rankTexts": {"equal": 0, "differing": 0},
        "positions": [], "maxRank": [], "icons": [], "names": [], "requires": [], "mismatches": [],
    }
    for cls, doc in sorted(docs.items()):
        for tree in doc["trees"]:
            for t in tree["talents"]:
                cid = t["source"].get("talentId")
                ent = by_id.get(cid)
                if ent is None:
                    res["unmatched"].append(f"{cls}/{tree['id']}/{t['id']}")
                    continue
                res["matched"] += 1
                _, _, p = ent
                where = {"class": cls, "tree": tree["id"], "talent": t["id"], "name": t["name"]}
                if (t["row"], t["col"]) != (p["row"], p["col"]):
                    res["positions"].append({**where, "datamined": [t["row"], t["col"]], "prior": [p["row"], p["col"]]})
                if t["maxRank"] != p["maxRank"]:
                    res["maxRank"].append({**where, "datamined": t["maxRank"], "prior": p["maxRank"]})
                if t["icon"] != p["icon"]:
                    res["icons"].append({**where, "datamined": t["icon"], "prior": p["icon"]})
                if normalise_text(t["name"]) != normalise_text(p["name"]):
                    res["names"].append({**where, "datamined": t["name"], "prior": p["name"]})
                qa = sorted((r["talent"], r["rank"]) for r in t.get("requires", []))
                qb = sorted((r["talent"], r["rank"]) for r in p.get("requires", []))
                if len(qa) != len(qb) or [x[1] for x in qa] != [x[1] for x in qb]:
                    res["requires"].append({**where, "datamined": qa, "prior": qb})
                for i in range(min(t["maxRank"], len(p.get("ranks") or []))):
                    a, b = _rendered(t, i), p["ranks"][i]
                    if normalise_text(a) == normalise_text(b):
                        res["rankTexts"]["equal"] += 1
                    else:
                        res["rankTexts"]["differing"] += 1
                        res["mismatches"].append({**where, "rank": i + 1, "datamined": a, "prior": b})
    n = res["rankTexts"]["equal"] + res["rankTexts"]["differing"]
    res["rankTexts"]["percent"] = round(100 * res["rankTexts"]["equal"] / n, 2) if n else 0.0
    res["rankTexts"]["talentsDiffering"] = len({(m["class"], m["talent"]) for m in res["mismatches"]})
    return res


def compare_markdown(res: dict) -> str:
    r = res["rankTexts"]
    out = ["# Datamined import vs. the Classic Era prior", "",
           f"- prior: {res['prior']['trees']} trees, {res['prior']['talents']} talents",
           f"- datamined: {res['datamined']['classes']} classes, {res['datamined']['trees']} trees, "
           f"{res['datamined']['talents']} talents",
           f"- matched by Talent.db2 id: {res['matched']}"
           + (f" (unmatched: {len(res['unmatched'])})" if res["unmatched"] else ""),
           f"- per-rank text equal after normalisation: **{r['equal']} / {r['equal'] + r['differing']} "
           f"= {r['percent']} %** ({r['talentsDiffering']} talents differ)",
           f"- position differences: {len(res['positions'])}, maxRank: {len(res['maxRank'])}, "
           f"prerequisites: {len(res['requires'])}, icons: {len(res['icons'])}, names: {len(res['names'])}", ""]
    for key, title in (("positions", "Positions"), ("maxRank", "maxRank"), ("requires", "Prerequisites"),
                       ("names", "Names"), ("icons", "Icons")):
        if res[key]:
            out += [f"## {title} ({len(res[key])})", "", "| talent | datamined | prior |", "|---|---|---|"]
            out += [f"| {x['class']}/{x['talent']} | `{x['datamined']}` | `{x['prior']}` |" for x in res[key]] + [""]
    out += [f"## Differing rank texts ({r['differing']})", ""]
    for m in res["mismatches"]:
        out += [f"- **{m['class']}/{m['talent']}** rank {m['rank']}",
                f"  - datamined: {m['datamined']}",
                f"  - prior:     {m['prior']}"]
    return "\n".join(out) + "\n"


# ----------------------------------------------------------------------------
# diff: datamined class file vs. the current canonical file
# ----------------------------------------------------------------------------

_WS_RE = re.compile(r"\s+")


def normalise_text(s: str) -> str:
    """Comparison form: lower case, collapsed whitespace, no trailing punctuation."""
    return _WS_RE.sub(" ", clean_text(s)).strip().lower().rstrip(". ")


def _rendered(t: dict, i: int) -> str:
    r = t["ranks"][i]
    return r if isinstance(r, str) else _fill(t["description"], r)


def _by_name(doc: dict) -> dict[str, tuple[dict, dict]]:
    out: dict[str, tuple[dict, dict]] = {}
    for tree in doc["trees"]:
        for t in tree["talents"]:
            out[normalise_text(t["name"])] = (tree, t)
    return out


def _req_names(doc: dict, reqs: list[dict]) -> list[tuple[str, int]]:
    index = {t["id"]: t["name"] for tree in doc["trees"] for t in tree["talents"]}
    return sorted((normalise_text(index.get(r["talent"], r["talent"])), r["rank"]) for r in reqs)


def diff_class(new: dict, old: dict) -> dict:
    """Compare a datamined class document with the canonical one, matching by talent name."""
    a, b = _by_name(new), _by_name(old)
    res: dict[str, Any] = {
        "class": new["class"], "build": new["trees"][0]["datamined"]["build"] if new["trees"] else None,
        "counts": {"datamined": len(a), "current": len(b)},
        "new": [], "gone": [], "position": [], "maxRank": [], "ranks": [], "requires": [], "icons": [], "tree": [],
    }
    for key in sorted(set(a) - set(b)):
        tree, t = a[key]
        res["new"].append({"name": t["name"], "tree": tree["id"], "row": t["row"], "col": t["col"], "id": t["id"]})
    for key in sorted(set(b) - set(a)):
        tree, t = b[key]
        res["gone"].append({"name": t["name"], "tree": tree["id"], "row": t["row"], "col": t["col"], "id": t["id"]})
    for key in sorted(set(a) & set(b)):
        (ta, na), (tb, nb) = a[key], b[key]
        where = {"name": na["name"], "id": na["id"], "currentId": nb["id"]}
        if ta["id"] != tb["id"]:
            res["tree"].append({**where, "datamined": ta["id"], "current": tb["id"]})
        if (na["row"], na["col"]) != (nb["row"], nb["col"]):
            res["position"].append({**where, "tree": ta["id"],
                                    "datamined": [na["row"], na["col"]], "current": [nb["row"], nb["col"]]})
        if na["maxRank"] != nb["maxRank"]:
            res["maxRank"].append({**where, "datamined": na["maxRank"], "current": nb["maxRank"]})
        if na["icon"] != nb["icon"]:
            res["icons"].append({**where, "datamined": na["icon"], "current": nb["icon"],
                                 "currentSource": nb["iconSource"]})
        ra = [normalise_text(_rendered(na, i)) for i in range(na["maxRank"])]
        rb = [normalise_text(_rendered(nb, i)) for i in range(nb["maxRank"])]
        for i in range(min(len(ra), len(rb))):
            if ra[i] != rb[i]:
                res["ranks"].append({**where, "rank": i + 1,
                                     "datamined": _rendered(na, i), "current": _rendered(nb, i)})
        # prerequisites compare by the *name* of the target: the two files have
        # independent id spaces and a renamed talent would otherwise read as a change
        qa = _req_names(new, na.get("requires", []))
        qb = _req_names(old, nb.get("requires", []))
        if qa != qb:
            res["requires"].append({**where, "datamined": qa, "current": qb})
    res["summary"] = {k: len(v) for k, v in res.items() if isinstance(v, list)}
    return res


def diff_markdown(diffs: list[dict]) -> str:
    out = ["# Datamined vs. current canonical data", ""]
    build = next((d["build"] for d in diffs if d.get("build")), "?")
    out += [f"Build `{build}`, matched by talent name (normalised).", "",
            "| class | talents (datamined / current) | new | gone | position | maxRank | ranks | requires | icons |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for d in diffs:
        s = d["summary"]
        out.append(f"| {d['class']} | {d['counts']['datamined']} / {d['counts']['current']} | "
                   f"{s['new']} | {s['gone']} | {s['position']} | {s['maxRank']} | {s['ranks']} | "
                   f"{s['requires']} | {s['icons']} |")
    for d in diffs:
        out += ["", f"## {d['class']}", ""]
        if d["new"]:
            out += ["**New (datamined only)**", ""]
            out += [f"- `{x['id']}` {x['name']} - {x['tree']} r{x['row']}c{x['col']}" for x in d["new"]] + [""]
        if d["gone"]:
            out += ["**Gone (current only)**", ""]
            out += [f"- `{x['id']}` {x['name']} - {x['tree']} r{x['row']}c{x['col']}" for x in d["gone"]] + [""]
        for key, title in (("tree", "Tree moved"), ("position", "Position"), ("maxRank", "maxRank"),
                           ("requires", "Prerequisites"), ("icons", "Icons")):
            if d[key]:
                out += [f"**{title}**", "", "| talent | datamined | current |", "|---|---|---|"]
                out += [f"| {x['name']} | `{x['datamined']}` | `{x['current']}` |" for x in d[key]] + [""]
        if d["ranks"]:
            out += [f"**Rank text ({len(d['ranks'])} differing rank(s))**", ""]
            for x in d["ranks"][:60]:
                out += [f"- **{x['name']}** rank {x['rank']}",
                        f"  - datamined: {x['datamined']}",
                        f"  - current:   {x['current']}"]
            if len(d["ranks"]) > 60:
                out.append(f"- ... {len(d['ranks']) - 60} more (see the JSON report)")
            out.append("")
    return "\n".join(out) + "\n"


__all__ = [
    "BUILDS_URL", "CLASS_BY_ID", "CSV_URL", "Db2", "Effect", "FALLBACK_ICON", "Log", "OPTIONAL_TABLES",
    "PAGES", "REQUIRED_TABLES", "RULES_CLASSIC", "RenderResult", "Renderer", "Spell", "TABLES", "TabRow",
    "TalentRow", "build_class_docs", "build_dir", "class_name", "csv_url", "diff_class", "diff_markdown",
    "compare_markdown", "compare_prior", "fetch", "highest_encoding_version", "iter_csv", "load",
    "normalise_text", "now_rfc3339",
    "read_manifest", "report_markdown", "sha256_file", "template_and_slots", "verify",
]
