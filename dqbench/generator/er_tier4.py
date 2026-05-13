"""ER Tier 4 dataset generator — Mistyped columns.

A diagnostic tier that mirrors T1's person-shape but deliberately mis-aligns
four column names with their content. The duplicate signal still exists in
realistic columns (email, phone), so a deduper that gates its per-column
refinements on profiled column type should score close to T1; a deduper that
trusts the column name will fire name/address scorers on noise and pay a
precision tax.

Mistyped columns (name disagrees with content):
- ``first_name``  → 12-char hex tokens (looks like an identifier)
- ``last_name``   → 6-8 digit numeric IDs
- ``address``     → free-form notes ("see Bob's directions")
- ``industry``    → people's names (instead of NAICS / industry labels)

Realistic columns (carry the duplicate signal):
- ``email``, ``phone``, ``city``, ``state``, ``zip``, ``company``
"""
from __future__ import annotations

import random

import polars as pl

from dqbench.er_ground_truth import ERGroundTruth
from dqbench.generator.utils import (
    FIRST_NAMES,
    LAST_NAMES,
    DOMAINS,
    CITIES,
    COMPANIES,
    PHONE_AREA_CODES,
)

NROWS = 800
N_UNIQUE = 720
N_DUPES = 80  # 40 email-case + 25 email-typo + 15 phone-format

HEX_ALPHABET = "0123456789abcdef"

# Short, repeatable note pool — collisions across rows are intentional so
# a token-based address scorer (without a col_type gate) over-credits unrelated
# rows that happen to share a template.
FREE_FORM_NOTES = [
    "see Bob's directions",
    "call before 5pm",
    "buzzer broken — knock loudly",
    "leave package with neighbor",
    "back entrance only after 6",
    "ring twice and wait",
    "ask for Sam at front desk",
    "side door is the office",
    "no signature required",
    "deliver to mailroom",
    "old warehouse, freight elevator",
    "next to the laundromat",
    "above the corner pharmacy",
    "white house with red shutters",
    "use the gate code on file",
]


def _hex_token(rng: random.Random, length: int = 12) -> str:
    return "".join(rng.choice(HEX_ALPHABET) for _ in range(length))


def _numeric_id(rng: random.Random) -> str:
    width = rng.randint(6, 8)
    lo = 10 ** (width - 1)
    hi = (10**width) - 1
    return str(rng.randint(lo, hi))


def _generate_phone(rng: random.Random) -> str:
    area = rng.choice(PHONE_AREA_CODES)
    return f"({area}) {rng.randint(200, 999)}-{rng.randint(1000, 9999)}"


def _generate_entity(rng: random.Random) -> dict[str, str]:
    real_first = rng.choice(FIRST_NAMES)
    real_last = rng.choice(LAST_NAMES)
    domain = rng.choice(DOMAINS)
    email = f"{real_first.lower()}.{real_last.lower()}@{domain}"
    city, state, zipcode = rng.choice(CITIES)
    # industry should hold a code/label; mistyped here as a person name.
    industry_first = rng.choice(FIRST_NAMES)
    industry_last = rng.choice(LAST_NAMES)
    return {
        "first_name": _hex_token(rng),
        "last_name": _numeric_id(rng),
        "email": email,
        "phone": _generate_phone(rng),
        "address": rng.choice(FREE_FORM_NOTES),
        "city": city,
        "state": state,
        "zip": zipcode,
        "company": rng.choice(COMPANIES),
        "industry": f"{industry_first} {industry_last}",
    }


def _email_case_dupe(entity: dict[str, str], rng: random.Random) -> dict[str, str]:
    dupe = entity.copy()
    dupe["email"] = dupe["email"].upper()
    dupe["first_name"] = _hex_token(rng)
    dupe["last_name"] = _numeric_id(rng)
    return dupe


def _email_typo_dupe(entity: dict[str, str], rng: random.Random) -> dict[str, str]:
    dupe = entity.copy()
    chars = list(dupe["email"])
    if len(chars) > 4:
        idx = rng.randint(1, len(chars) - 3)
        chars[idx], chars[idx + 1] = chars[idx + 1], chars[idx]
        dupe["email"] = "".join(chars)
    dupe["first_name"] = _hex_token(rng)
    dupe["last_name"] = _numeric_id(rng)
    return dupe


def _phone_format_dupe(entity: dict[str, str], rng: random.Random) -> dict[str, str]:
    dupe = entity.copy()
    phone = (
        dupe["phone"]
        .replace("(", "")
        .replace(")", "")
        .replace(" ", "")
        .replace("-", "")
    )
    dupe["phone"] = phone
    dupe["first_name"] = _hex_token(rng)
    dupe["last_name"] = _numeric_id(rng)
    return dupe


def generate_er_tier4() -> tuple[pl.DataFrame, ERGroundTruth]:
    """Generate the ER Tier 4 (Mistyped) benchmark dataset."""
    rng = random.Random(42)

    entities: list[dict[str, str]] = []
    for _ in range(N_UNIQUE):
        entities.append(_generate_entity(rng))

    source_indices = rng.sample(range(N_UNIQUE), N_DUPES)

    dupe_fns = (
        [_email_case_dupe] * 40
        + [_email_typo_dupe] * 25
        + [_phone_format_dupe] * 15
    )
    assert len(dupe_fns) == N_DUPES

    duplicate_pairs: list[tuple[int, int]] = []
    dupe_rows: list[dict[str, str]] = []

    for i, src_idx in enumerate(source_indices):
        dupe_row_idx = N_UNIQUE + len(dupe_rows)
        dupe_rows.append(dupe_fns[i](entities[src_idx], rng))
        duplicate_pairs.append((src_idx, dupe_row_idx))

    all_rows = entities + dupe_rows
    assert len(all_rows) == NROWS

    indices = list(range(NROWS))
    rng.shuffle(indices)
    shuffled_rows = [all_rows[i] for i in indices]

    old_to_new = {old: new for new, old in enumerate(indices)}
    remapped_pairs = [
        (min(old_to_new[a], old_to_new[b]), max(old_to_new[a], old_to_new[b]))
        for a, b in duplicate_pairs
    ]
    remapped_pairs.sort()

    df = pl.DataFrame(shuffled_rows)

    gt = ERGroundTruth(
        tier=4,
        version="1.0.0",
        rows=NROWS,
        duplicate_pairs=remapped_pairs,
        total_duplicates=N_DUPES,
        difficulty="mistyped",
    )

    return df, gt
