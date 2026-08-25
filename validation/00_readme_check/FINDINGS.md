# 0. Was the README's worked example actually regenerated?

**Script:** `check.py`. Raw output: `output.txt`. No library code was changed.

## Question asked

The README (`## Checking that the answer actually worked`) shows this
output block:

```
c0:overall: 50.0% win rate [18.8%, 81.2%] (3/6 decisive pairs, 0 ties)
c1:overall: 50.0% win rate [18.8%, 81.2%] (3/6 decisive pairs, 0 ties)
...
spread across 6 candidates: 50.0%–50.0% (sd 0.000, 0.00x sampling noise)
warning: win rates are not clearly separated from what pure sampling noise
would produce — the judge may not be discriminating between these candidates.
```

Under the corrected (both-orders-resolve-to-one-outcome) logic, K reference
comparisons should produce K decisive pairs, not 2K. Does this block come
from an actual run of the current code, with 6 references?

## Finding: no — this block was hand-authored, not regenerated

Running `examples/worked_example.py` (the only script in the repo that
builds a love pool and prints win rates) produces this instead:

```
 strong: win rate 50% [9%, 91%] over 2 decisive pairs (0 tied), order-disagreement 0%
   weak: win rate 50% [9%, 91%] over 2 decisive pairs (0 tied), order-disagreement 0%
...
six candidates, each 50%: spread 50%–50%, 0.00x sampling noise
  -> discriminating: False (this is the failure mode, caught)
```

Three separate things are wrong with treating the README block as real output:

1. **Different candidates, different format.** The worked example only ever
   scores two candidates (`strong`, `weak`), never `c0`..`c5`, and its
   `print()` calls (`examples/worked_example.py:63-67` and `:122-127`) don't
   produce `"cN:overall: ..."` or `"(K/N decisive pairs, T ties)"` — that
   exact phrasing comes from `src/hibiscus/cli/score_cmd.py:66-70` and `:125`,
   i.e. the **CLI's** `hibiscus score` output format. The README block is
   formatted like a `hibiscus score` run, but no `hibiscus compare` /
   `hibiscus score` invocation producing 6 candidates each with 6 references
   appears anywhere in the repo.

2. **The one place "6" appears is a different, uncounterbalanced demo.**
   `run_spread_check()` in `worked_example.py` (lines 103-119) hand-builds
   `ComparisonRecord` objects directly — 6 candidates x 6 references — but
   gives each pair only **one** order (`"candidate_first"`), never
   `"reference_first"`. `resolve_pairs` still resolves a single-order pair
   to a definite win/loss (see `pairs.py:130`, `counterbalanced=False` but a
   decisive outcome), so this demo happens to produce "6 decisive pairs, 0
   ties" per candidate — but it does so by *never exercising the
   both-orders resolution the section is about*. It's a different
   construction that coincidentally produces the right pair count, not the
   both-orders-collapsing-into-one-outcome behavior the prose claims to
   demonstrate.

3. **The numbers are arithmetically self-consistent, but that's necessary,
   not sufficient.** `wilson_interval(3, 6)` today does compute exactly
   `50.0% [18.8%, 81.2%]` (see `output.txt`, section 3) — so whoever wrote
   the README block plugged real numbers into the real formula. But nothing
   in the current repo emits that exact text as a side effect of running
   anything, in either the CLI or the example script. It reads as
   hand-computed illustrative prose, not a captured transcript.

**Consequence:** the worked-example claim in the README ("Builds a
five-item love-tier pool... shows the spread check catching a set where
nothing separates") is accurate for the *actual* `worked_example.py`, which
does use 5 references and does correctly show 2 decisive pairs per
candidate (matching the "K references -> K decisive pairs" fix). But the
separate illustrative block for the CLI-shaped 6-candidate case was never
run against the current code and should either be regenerated from a real
`hibiscus compare` + `hibiscus score` invocation, or removed/marked as
illustrative rather than presented as output.

## Secondary question: is MockJudge order-dependent?

Checked empirically: 60 candidates x k=2 references x both orders (240 raw
`MockJudge` calls) — **0/60 candidates showed any order-disagreement**,
and no judge-reported ties occurred either.

This is *not* a coincidence and *not* evidence of a real judge's behavior.
`MockJudge.compare(text_a, text_b, question)` hashes `text_a` and `text_b`
independently and picks whichever hash is smaller. Swapping which text
occupies the "a" role and which occupies "b" swaps which digest is
compared, but the *pair of digests being compared* is unchanged — the
decision reduces to "does candidate-text or reference-text hash lower,"
independent of which one is shown first. So `MockJudge` (default
`tie_rate=0`) is order-independent **by construction**. This is already
called out in its docstring ("it compares content symmetrically, so it
shows no position bias; that is a property of the mock, not evidence about
real judges"), but it has a concrete consequence worth surfacing: **every
demo built on MockJudge (the worked example, and any README prose drawn
from it) can never show a real order-disagreement tie** — 0% is
guaranteed, not measured. The library's actual unit tests do correctly
exercise the order-disagreement code path, but via a dedicated
position-biased test double (`AlwaysAJudge` in `tests/test_compare.py`)
and hand-built fixtures (`tests/test_pairs.py`), not via `MockJudge`. So the
underlying logic is fine and tested; it's specifically the illustrative
worked-example narrative that cannot demonstrate this particular failure
mode with the judge it uses.

## Bottom line

- The worked example's *actual* pool size (5) and *actual* per-candidate
  decisive-pair count (2) are consistent with the corrected "N references
  -> N decisive pairs" behavior — that part checks out.
- The specific 6-candidate output block quoted in the README does not come
  from running any current script and should be treated as unverified prose
  until regenerated.
- MockJudge's "0 ties" is expected and uninformative about real judges by
  construction, not a bug — but it does mean no demo in this repo currently
  shows what an order-disagreement tie looks like end-to-end with a
  realistic (non-hand-built) data path.
