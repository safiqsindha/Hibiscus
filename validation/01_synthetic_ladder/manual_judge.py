"""A JudgeAdapter backed by verdicts a human/LLM (me, Claude, this session)
produced by actually reading each pair -- standing in for AnthropicJudge
since no ANTHROPIC_API_KEY / `anthropic` package is available in this
sandbox (see FINDINGS.md, "Real judge access").

Important limitation, disclosed here and in FINDINGS.md: I judge each
(candidate, reference) pair ONCE, based on content, and that single
preference is looked up regardless of which text is passed as text_a vs
text_b. That means this adapter is, by construction, immune to position
bias -- it cannot exhibit order-disagreement the way a real single-shot
API call blindly re-asked in each order could. It validates whether
real semantic judgment recovers the intended quality ordering; it does
NOT validate a real judge's susceptibility to position bias.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from hibiscus.judge.base import JudgeAdapter, JudgeVerdict  # noqa: E402


class ManualJudge(JudgeAdapter):
    def __init__(self, verdicts_by_text_pair: dict):
        self._verdicts = verdicts_by_text_pair
        self.calls = 0

    def compare(self, text_a: str, text_b: str, question: str) -> JudgeVerdict:
        self.calls += 1
        key = frozenset((text_a, text_b))
        if key not in self._verdicts:
            raise KeyError(
                "no manual verdict recorded for this text pair "
                f"(lens {len(text_a)}, {len(text_b)}) -- add it to manual_verdicts.json"
            )
        pref = self._verdicts[key]
        if pref == "TIE":
            return JudgeVerdict(winner="tie", raw_response="manual:tie")
        winner = "a" if pref == text_a else "b"
        return JudgeVerdict(winner=winner, raw_response=f"manual:{winner}")


def load_manual_judge(verdicts_path: "str | Path", id_to_text: dict) -> ManualJudge:
    with Path(verdicts_path).open("r", encoding="utf-8") as fh:
        data = json.load(fh)

    verdicts_by_text_pair: dict = {}
    for row in data["verdicts"]:
        cand_text = id_to_text[row["candidate_id"]]
        ref_text = id_to_text[row["reference_id"]]
        verdict = row["verdict"]
        if verdict == "tie":
            value = "TIE"
        elif verdict == "candidate":
            value = cand_text
        elif verdict == "reference":
            value = ref_text
        else:
            raise ValueError(f"unknown verdict {verdict!r} for {row}")
        verdicts_by_text_pair[frozenset((cand_text, ref_text))] = value

    return ManualJudge(verdicts_by_text_pair)
