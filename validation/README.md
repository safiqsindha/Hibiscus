# External validation of Hibiscus's pair-resolution fix

Four checks, run in order, against data outside the library's own test
suite. No library code was changed by any of these — each is a
standalone script plus a findings write-up. Run each script from inside
its own directory (`cd validation/0N_*/ && python run_*.py`); `pip install
-e .` (and, for `01`/`02`, no extra dependencies beyond `scipy`/`numpy` for
the independent cross-check in `02`) is enough to reproduce all of it.

| # | Check | Status | One-line result |
|---|-------|--------|------------------|
| 0 | [README worked-example regenerated?](00_readme_check/FINDINGS.md) | Done | No — the "3/6 decisive pairs" block doesn't come from any script in the repo; MockJudge is order-independent by construction, so its "0 ties" is expected, not evidence. |
| 1 | [Synthetic degradation ladder](01_synthetic_ladder/FINDINGS.md) | Done | MockJudge: plumbing runs cleanly, ~57-71% band with no real separation (expected — it has no taste). Real judge (me, 60-pair subset, no API key available): 40/40 degraded-vs-intact judgments correctly favored intact, including the padded/length-bias probe; null control showed zero spurious spread, unlike MockJudge's. |
| 2 | [SummEval correlation check](02_summeval/FINDINGS.md) | Done | `hibiscus report`'s Pearson math matches an independent scipy/numpy implementation exactly (max diff 0.0) on real, non-synthetic data (6,400 rows). No pair crosses the 0.85 threshold on this dataset at this aggregation level — an honestly-reported negative result, not a failure. |
| 3 | [Wikipedia quality classes](03_wikipedia/FINDINGS.md) | **Blocked** | This sandbox's network egress policy rejects `en.wikipedia.org` and every mirror/alternative checked (403, policy denial) — not something to route around. See that file for options. |

## Headline findings that matter beyond "did the script run"

1. **The README's illustrative output block for the both-orders fix was
   never regenerated from the current code** (validation 0). The actual
   worked example is fine and consistent with the fix; a separate quoted
   block is not real output and should be fixed or removed.
2. **MockJudge cannot exercise order-disagreement or expose length bias**
   by construction — every demo/test built on it that touches those paths
   is either using a different, purpose-built stub judge (which the real
   unit tests correctly do) or getting a guaranteed, uninformative answer
   (which the worked example does). This isn't a defect, but it's worth
   knowing when reading demo output as if it were evidence.
3. **The pair-resolution and correlation math are both independently
   verified correct** on non-synthetic data: the synthetic ladder's real
   judge pass recovered 100% of the constructed ground truth, and the
   SummEval correlation matrix matched an independent scipy implementation
   bit-for-bit.
4. **`score_spread`'s "discriminating" flag is only as good as the judge
   feeding it** — it flagged MockJudge's null-control set (20 near-identical
   texts) as discriminating (hash noise, not signal), while the same
   check under real judgment correctly found no spread at all.
5. **Wikipedia-based validation remains open**, blocked by this
   environment's network policy rather than by anything in Hibiscus.

## What none of this validates

No check here exercises the real `AnthropicJudge` adapter — no
`ANTHROPIC_API_KEY` (or `anthropic` package) is available in this sandbox.
Where "a real judge" was needed (validation 1's subset), I read each pair
myself and recorded a genuine verdict, which validates the scoring and
aggregation logic given honest judgment, but cannot say anything about a
real API-based judge's susceptibility to position bias or length bias
specifically — see the limitation section in `01_synthetic_ladder/FINDINGS.md`.
