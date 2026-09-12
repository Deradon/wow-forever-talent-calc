#!/usr/bin/env python3
"""Normalise the raw Classic Era downloads into talents.json.

Inputs (see SOURCES.md):
    raw/talents-classic.js   Wowhead classic talent calculator data (structure, no text)
    raw/spells.json          melv-n/wow-talent-calculator spells.json (name, icon, rank, description)

Output:
    talents.json             class -> trees -> talents, shape close to docs/DATA-SCHEMA.md

Standard library only. Run from anywhere:
    python3 data/prior/classic-era/build.py
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
OUT = HERE / "talents.json"

CLASSES = ["druid", "hunter", "mage", "paladin", "priest", "rogue", "shaman", "warlock", "warrior"]
# Wowhead role codes as used in talents-classic.js (best-effort mapping, informational only)
WOWHEAD_ROLE = {1: "healer", 2: "dps", 3: "tank"}
# Wowhead's internal tab names differ from the in-game tree names for four trees
TREE_NAME_OVERRIDE = {381: "Retribution", 261: "Elemental", 302: "Affliction", 303: "Demonology"}
# numbers (incl. leading-dot decimals) and words. Only tokens that vary between
# ranks become {n} placeholders; a word that varies only by a trailing plural "s"
# becomes a "" / "s" slot (DATA-SCHEMA.md section 5), everything else stays literal
TOKEN_RE = re.compile(r"\d+(?:\.\d+)?|(?<!\d)\.\d+|[A-Za-z]+")
NUM_RE = re.compile(r"^(?:\d+(?:\.\d+)?|\.\d+)$")


def slug(name: str) -> str:
    s = unicodedata.normalize("NFKD", name)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = s.replace("'", "").replace("’", "")
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def clean_text(s: str) -> str:
    s = s.replace(" ", " ").replace("’", "'").replace("“", '"').replace("”", '"')
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()


def split_tree_name(desc: str) -> tuple[str, str]:
    """'MageFire' -> ('mage', 'Fire'); 'HunterBeastMastery' -> ('hunter', 'Beast Mastery')."""
    for cls in CLASSES:
        if desc.lower().startswith(cls):
            rest = desc[len(cls):]
            words = re.findall(r"[A-Z][a-z]*", rest)
            return cls, " ".join(words)
    raise ValueError(f"unknown class in tree description {desc!r}")


def _stem(word: str) -> str:
    return word[:-1] if len(word) > 1 and word.endswith("s") else word


def _skeleton(text: str) -> str:
    return TOKEN_RE.sub(lambda m: "\x00" if NUM_RE.match(m.group()) else _stem(m.group()), text)


def template_and_slots(rank_texts: list[str]) -> tuple[str | None, list[list[float | int | str]] | None, str | None]:
    """Turn per-rank texts into a {n}-template plus per-rank slot values.

    Numbers that differ between ranks become numeric placeholders, words that
    differ only by a plural "s" become "" / "s" placeholders, everything else
    stays literal. Returns (None, None, reason) when the sentence shape changes
    (different units, extra sentences, ...).
    """
    if len(rank_texts) == 1:
        return rank_texts[0], [[]], None
    if len({_skeleton(t) for t in rank_texts}) != 1:
        return None, None, "sentence shape changes between ranks"
    tokens = [TOKEN_RE.findall(t) for t in rank_texts]
    n = len(tokens[0])
    varying = [i for i in range(n) if len({row[i] for row in tokens}) > 1]
    idx = {pos: k for k, pos in enumerate(varying)}
    parts: list[str] = []
    last = 0
    for pos, m in enumerate(TOKEN_RE.finditer(rank_texts[0])):
        parts.append(rank_texts[0][last:m.start()])
        if pos not in idx:
            parts.append(m.group(0))
        elif NUM_RE.match(m.group(0)):
            parts.append("{%d}" % idx[pos])
        else:  # plural slot: literal stem + placeholder for "" / "s"
            parts.append(_stem(m.group(0)) + "{%d}" % idx[pos])
        last = m.end()
    parts.append(rank_texts[0][last:])
    template = "".join(parts)

    def value(s: str) -> float | int | str:
        if not NUM_RE.match(s):
            return "s" if s.endswith("s") else ""
        return float(s) if "." in s else int(s)

    slots = [[value(row[i]) for i in varying] for row in tokens]
    return template, slots, None


def main() -> int:
    js = (RAW / "talents-classic.js").read_text(encoding="utf-8")
    data, _ = json.JSONDecoder().raw_decode(js[js.index("{"):])
    spells = json.loads((RAW / "spells.json").read_text(encoding="utf-8"))

    classes: dict[str, dict] = {cls: {"className": cls.capitalize(), "trees": []} for cls in CLASSES}
    missing_spells: list[int] = []
    shape_changes = 0

    for tab_id, tree in data["trees"].items():
        cls, tree_name = split_tree_name(tree["description"])
        tree_name = TREE_NAME_OVERRIDE.get(int(tab_id), tree_name)
        talents_raw = data["talents"][tab_id]
        tree_id = slug(tree_name)
        id_by_talent: dict[int, str] = {}
        talents = []
        for tal in sorted(talents_raw.values(), key=lambda t: (t["row"], t["col"])):
            spell_ids = tal["ranks"]
            rank_recs = [spells.get(str(sid)) for sid in spell_ids]
            for sid, rec in zip(spell_ids, rank_recs):
                if rec is None:
                    missing_spells.append(sid)
            first = next((r for r in rank_recs if r), None)
            name = clean_text(first["name"]) if first else f"talent-{tal['id']}"
            rank_texts = [clean_text(r["description"]) if r else "" for r in rank_recs]
            template, slots, reason = template_and_slots(rank_texts)
            if reason:
                shape_changes += 1
            tid = slug(name)
            id_by_talent[tal["id"]] = tid
            talents.append({
                "classicTalentId": tal["id"],
                "id": tid,
                "name": name,
                "row": tal["row"],
                "col": tal["col"],
                "maxRank": len(spell_ids),
                "icon": tal["icon"],
                "requires": [{"classicTalentId": r["id"], "rank": r["qty"]} for r in tal.get("requires", [])],
                "spellIds": spell_ids,
                "ranks": rank_texts,
                "description": template,
                "slots": slots,
                **({"note": reason} if reason else {}),
            })
        classes[cls]["trees"].append({
            "id": tree_id,
            "name": tree_name,
            "classicTabId": int(tab_id),
            "role": WOWHEAD_ROLE.get(tree.get("role"), None),
            "wowheadRole": tree.get("role"),
            "talents": talents,
            "_id_by_talent": id_by_talent,
        })

    # finish: tree order (alphabetical == in-game order for all Classic classes),
    # resolve requires ids, disambiguate talent id collisions within a class
    for cls, cdoc in classes.items():
        trees = sorted(cdoc["trees"], key=lambda t: t["id"])
        for i, t in enumerate(trees):
            t["order"] = i
        counts = Counter(t["id"] for tree in trees for t in tree["talents"])
        for tree in trees:
            for t in tree["talents"]:
                if counts[t["id"]] > 1:
                    t["id"] = f"{t['id']}-{tree['id']}"
            tree["_id_by_talent"] = {k: (v if counts[v] == 1 else f"{v}-{tree['id']}") for k, v in tree["_id_by_talent"].items()}
        for tree in trees:
            idmap = tree.pop("_id_by_talent")
            for t in tree["talents"]:
                for r in t["requires"]:
                    r["talent"] = idmap.get(r["classicTalentId"], f"talent-{r['classicTalentId']}")
                    if r["classicTalentId"] not in idmap:
                        print(f"warning: {cls}/{tree['id']}/{t['id']} requires talent {r['classicTalentId']} from another tree", file=sys.stderr)
            tree_keys = ["id", "name", "classicTabId", "order", "role", "wowheadRole", "talents"]
            for k in list(tree):
                if k not in tree_keys:
                    del tree[k]
        cdoc["trees"] = [{k: tree[k] for k in ["id", "name", "classicTabId", "order", "role", "wowheadRole", "talents"]} for tree in trees]

    out = {
        "source": "Wowhead classic talent data (structure) + melv-n/wow-talent-calculator spells.json (text); see SOURCES.md",
        "retrievedAt": "2026-09-13",
        "game": "World of Warcraft Classic Era, as served by Wowhead's Classic talent calculator on the retrieval date",
        "shape": {
            "classes": "class id -> { className, trees[] }",
            "tree": "id (slug of tree name), name, classicTabId (TalentTab.ID), order (left-to-right), role, talents[] sorted by (row, col)",
            "talent": "classicTalentId (Talent.ID), id (slug, unique per class), name, row, col, maxRank, icon, requires[{talent, classicTalentId, rank}], spellIds[per rank], ranks[per-rank tooltip text], description ({n} template over numbers that change per rank, null if the sentence shape changes), slots[per rank: values for the {n} placeholders]",
        },
        "classes": classes,
    }
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    n_trees = sum(len(c["trees"]) for c in classes.values())
    n_tal = sum(len(t["talents"]) for c in classes.values() for t in c["trees"])
    n_ranks = sum(t["maxRank"] for c in classes.values() for tr in c["trees"] for t in tr["talents"])
    n_req = sum(1 for c in classes.values() for tr in c["trees"] for t in tr["talents"] if t["requires"])
    print(f"classes {len(classes)}, trees {n_trees}, talents {n_tal}, rank spells {n_ranks}, "
          f"with prerequisites {n_req}, shape-changing {shape_changes}, missing spell texts {len(missing_spells)}")
    if missing_spells:
        print("missing:", missing_spells[:20], file=sys.stderr)
    return 0 if (len(classes), n_trees, n_tal, n_ranks) == (9, 27, 432, 1357) and not missing_spells else 1


if __name__ == "__main__":
    sys.exit(main())
