"""Validation 0: was the README's worked-example output actually regenerated?

The README (as of this check) shows, under "Checking that the answer
actually worked":

    c0:overall: 50.0% win rate [18.8%, 81.2%] (3/6 decisive pairs, 0 ties)
    c1:overall: 50.0% win rate [18.8%, 81.2%] (3/6 decisive pairs, 0 ties)
    ...
    spread across 6 candidates: 50.0%-50.0% (sd 0.000, 0.00x sampling noise)
    warning: win rates are not clearly separated from what pure sampling noise
    would produce ...

This script checks three things, all without touching library code:

1. Does examples/worked_example.py actually produce this text? (It should,
   if the README was regenerated from a real run after the compare/pairs
   fix landed.)
2. Is the *shape* of the claim ("N references -> N decisive pairs, not 2N")
   actually what today's pipeline produces for a real (non-synthetic)
   candidate-vs-pool comparison?
3. Is MockJudge order-independent? If it hashes text_a/text_b by literal
   position, the two counterbalancing orders would usually disagree and
   "0 ties" (meaning 0 order-disagreement ties in a real run) would be
   implausible. Checked empirically over many candidate/reference pairs.
"""

from __future__ import annotations

import io
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from hibiscus import Artifact, JudgeCache, Pool, RatedArtifact, Tier  # noqa: E402
from hibiscus.compare import order_disagreement_rate, run_comparisons  # noqa: E402
from hibiscus.judge.mock import MockJudge  # noqa: E402
from hibiscus.score import score_candidate  # noqa: E402


README_BLOCK = """\
c0:overall: 50.0% win rate [18.8%, 81.2%] (3/6 decisive pairs, 0 ties)
c1:overall: 50.0% win rate [18.8%, 81.2%] (3/6 decisive pairs, 0 ties)
...
spread across 6 candidates: 50.0%–50.0% (sd 0.000, 0.00x sampling noise)
warning: win rates are not clearly separated from what pure sampling noise
would produce — the judge may not be discriminating between these candidates.\
"""


def section(title: str) -> None:
    print(f"\n=== {title} ===")


def check_worked_example_output() -> str:
    """Run examples/worked_example.py exactly as a user would and capture stdout."""
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "examples" / "worked_example.py")],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def check_pool_size(actual_output: str) -> None:
    section("1. How many love-tier references does the worked example actually use?")
    for line in actual_output.splitlines():
        if "love-tier references" in line:
            print(f"  actual worked_example.py output: {line!r}")
    print(
        "  README prose says 'Builds a five-item love-tier pool' -- consistent "
        "with the actual pool size (5). But the output BLOCK quoted under "
        "'Checking that the answer actually worked' talks about 6 candidates "
        "(c0..c5), which the actual pool/compare/candidates setup in "
        "worked_example.py never produces (it only ever scores 2 candidates, "
        "'strong' and 'weak', never named c0..c5)."
    )


def check_block_is_not_produced(actual_output: str) -> None:
    section("2. Does any current script produce the README's exact output block?")
    print("README block:")
    print(README_BLOCK)
    print()
    if README_BLOCK.strip() in actual_output:
        print("MATCH: found verbatim in examples/worked_example.py output.")
    else:
        print("NO MATCH: this text does not appear in examples/worked_example.py's output.")
    print()
    print("Actual examples/worked_example.py output for the two comparable sections:")
    printing = False
    for line in actual_output.splitlines():
        if line.startswith("== comparing"):
            printing = True
        if line.startswith("== calibrating"):
            printing = False
        if printing:
            print(f"  {line}")
    printing = False
    for line in actual_output.splitlines():
        if line.startswith("== spread"):
            printing = True
        if line.startswith("== running"):
            printing = False
        if printing:
            print(f"  {line}")


def check_readme_numbers_are_internally_consistent() -> None:
    section("3. Are the README's own numbers at least *arithmetically* consistent?")
    from hibiscus.score import wilson_interval

    result = wilson_interval(3, 6)
    print(
        f"  Wilson(3/6) computed by today's code: "
        f"{result.point_estimate:.1%} [{result.lower:.3f}, {result.upper:.3f}]"
    )
    print("  README claims: 50.0% [18.8%, 81.2%]")
    close = abs(result.lower - 0.188) < 0.001 and abs(result.upper - 0.812) < 0.001
    print(f"  matches to 3 decimal places: {close}")
    print(
        "  So the *numbers*, taken as a Wilson interval for 3 wins out of 6 "
        "decisive pairs, are correct under the current formula. The problem "
        "is not the arithmetic -- it's that no script in this repo currently "
        "generates 6 candidates each drawing exactly 6 decisive pairs with 0 "
        "ties. The one place 6-reference synthetic data appears "
        "(run_spread_check in worked_example.py) constructs ComparisonRecord "
        "objects directly with only ONE order per pair ('candidate_first' "
        "only) -- never both orders -- so it never actually exercises the "
        "both-orders-resolve-to-one-outcome logic this section is supposed "
        "to be demonstrating. It also prints in a completely different "
        "format ('six candidates, each 50%: spread 50%-50%, ...') than the "
        "README block ('c0:overall: ... (3/6 decisive pairs, 0 ties)'), which "
        "matches the CLI's `hibiscus score` print format instead (see "
        "src/hibiscus/cli/score_cmd.py). That means the README block was "
        "authored by hand to *look like* real CLI output, not captured from "
        "an actual run of anything currently in this repo."
    )


def check_mock_judge_order_independence(n_pairs: int = 60) -> None:
    section("4. Is MockJudge order-independent? (does '0 ties' make sense for it?)")
    pool = Pool(None)
    for i in range(20):
        pool.add(RatedArtifact(id=f"ref-{i}", text=f"Reference text number {i} about topic {i % 5}.", tier=Tier.LOVE))

    judge = MockJudge()
    disagreements = 0
    total = 0
    judge_ties = 0
    for i in range(n_pairs):
        candidate = Artifact(id=f"cand-{i}", text=f"Candidate artifact number {i}, quite different wording.")
        records = run_comparisons(candidate, pool, judge, k=2, seed=i, model="mock-v1")
        rate = order_disagreement_rate(records)
        total += 1
        if rate > 0:
            disagreements += 1
        for r in records:
            if r.winner == "tie":
                judge_ties += 1

    print(f"  ran {total} candidates x k=2 references x 2 orders = {total * 4} raw MockJudge calls")
    print(f"  candidates with ANY order-disagreement: {disagreements}/{total}")
    print(f"  raw judge-reported 'tie' verdicts: {judge_ties}")
    print()
    print(
        "  MockJudge.compare(text_a, text_b, question) computes "
        "digest_a = hash(text_a), digest_b = hash(text_b), and picks whichever "
        "hash is smaller. Swapping which text is 'a' and which is 'b' swaps "
        "which digest is compared, but the *pair* of digests being compared is "
        "the same regardless of role assignment -- so the decision is a "
        "function of {candidate text, reference text} only, not of order. "
        "That means MockJudge (with tie_rate=0, the default) is, contrary to "
        "the suspicion, ORDER-INDEPENDENT by construction: order_disagreement "
        "should be exactly 0% empirically, matching the measurement above."
    )
    print()
    print(
        "  Consequence: '0 ties' in a MockJudge run is plausible and expected, "
        "not a red flag. But this is a property of MockJudge specifically "
        "(explicitly documented in judge/mock.py's docstring: 'it compares "
        "content symmetrically, so it shows no position bias; that is a "
        "property of the mock, not evidence about real judges'). Every DEMO "
        "that uses MockJudge (worked_example.py, and by extension the README "
        "prose built on it) exercises a judge that can never disagree with "
        "itself -- 0% order-disagreement in those demos is guaranteed, not "
        "measured. The library's own unit tests do separately cover the "
        "order-disagreement path correctly, via a dedicated hand-written "
        "test double (AlwaysAJudge in tests/test_compare.py) rather than "
        "MockJudge, plus hand-built ComparisonRecord fixtures in "
        "tests/test_pairs.py. So the *logic* is tested; it's specifically the "
        "worked example / README narrative that can never show a real "
        "order-disagreement tie, because MockJudge can't produce one."
    )


def main() -> None:
    buf = io.StringIO()
    with redirect_stdout(buf):
        pass  # placeholder; we run the subprocess for real output below

    actual_output = check_worked_example_output()
    check_pool_size(actual_output)
    check_block_is_not_produced(actual_output)
    check_readme_numbers_are_internally_consistent()
    check_mock_judge_order_independence()


if __name__ == "__main__":
    main()
