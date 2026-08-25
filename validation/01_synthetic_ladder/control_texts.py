"""20 near-identical texts: minor rewordings of the same paragraph, with no
real quality difference between them. Used as the spread-check control --
`score_spread` should report these as NOT discriminating, since there is
no true quality signal to find.
"""

from __future__ import annotations

_BASE = (
    "The night market opens once the heat breaks, and vendors light their "
    "lanterns row by row until the whole street glows orange. A noodle "
    "cart at the corner has served the same three dishes for as long as "
    "anyone remembers, and the line for it never really shortens. Steam "
    "drifts up past the awnings and mixes with the smell of grilled "
    "skewers from the stall next door. Regulars know to come early for "
    "the good seats, the low stools near the griddle where the heat still "
    "reaches you. By midnight the crowd thins, but a few tables stay full "
    "until the vendors start packing up their carts for the walk home."
)

# Each variant swaps a handful of words/phrases for close synonyms or
# reorders a clause, keeping meaning and quality constant.
_SUBSTITUTIONS: list[dict[str, str]] = [
    {},
    {"opens once the heat breaks": "opens as soon as the heat breaks", "glows orange": "glows a warm orange"},
    {"vendors light their lanterns": "vendors set out their lanterns", "row by row": "one row at a time"},
    {"has served the same three dishes": "has served the same three plates", "never really shortens": "rarely gets any shorter"},
    {"Steam drifts up": "Steam rises up", "mixes with the smell of": "blends with the scent of"},
    {"grilled skewers": "charcoal skewers", "stall next door": "stand next door"},
    {"Regulars know to come early": "Regulars learn to arrive early", "the good seats": "the best seats"},
    {"the low stools near the griddle": "the low stools by the griddle", "still reaches you": "still warms you"},
    {"By midnight the crowd thins": "By midnight the crowd starts to thin", "stay full": "remain full"},
    {"vendors start packing up their carts": "vendors begin packing their carts", "the walk home": "the trip home"},
    {"once the heat breaks": "the moment the heat breaks", "row by row": "one after another"},
    {"noodle cart at the corner": "noodle stall on the corner"},
    {"for as long as anyone remembers": "for longer than anyone can recall"},
    {"the line for it never really shortens": "the line for it almost never gets shorter"},
    {"past the awnings": "over the awnings"},
    {"good seats": "better seats", "still reaches you": "you can still feel"},
    {"a few tables stay full": "a handful of tables stay full"},
    {"start packing up": "begin to pack up"},
    {"whole street glows orange": "whole street turns a warm orange"},
    {"anyone remembers": "anyone can remember", "never really shortens": "hardly ever shortens"},
]


def _apply(text: str, subs: dict[str, str]) -> str:
    for old, new in subs.items():
        text = text.replace(old, new)
    return text


CONTROLS: list[tuple[str, str]] = [
    (f"ctl-{i:02d}", _apply(_BASE, subs)) for i, subs in enumerate(_SUBSTITUTIONS)
]

assert len(CONTROLS) == 20
assert len({t for _, t in CONTROLS}) == 20, "control variants must all be distinct strings"
