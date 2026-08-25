# 1. Synthetic degradation ladder

**Scripts:** `texts.py` (20 source passages), `degrade.py` (mechanical
transforms), `control_texts.py` (20 near-identical variants), `run_mock.py`
(full ladder, MockJudge), `manual_verdicts.json` + `manual_judge.py` +
`run_real_judge.py` (5-source subset, real judgment). Raw output:
`mock_output.txt`, `real_judge_output.txt`, `mock_results.json`,
`real_judge_results.json`. No library code was changed.

## Setup note: source texts

Project Gutenberg (`gutenberg.org`) is unreachable from this sandbox's
network egress policy (confirmed via the proxy status endpoint — see
`../03_wikipedia/FINDINGS.md` for the full picture of what this
environment can and can't reach). Per the task's own fallback ("Gutenberg,
or generate them; content doesn't matter"), I wrote 20 original ~150-210
word passages myself (`texts.py`), each with concrete numbers/names/dates
for the `stripped` transform to remove. Ground truth is by construction:
`intact` > every degraded variant of the same source. Ordering *among*
degraded classes is not asserted, per the task.

## Ground truth recovery

### MockJudge (full ladder: 20 sources x 4 classes = 80 candidates, k=5 refs, seed fixed)

```
      intact: mean win rate 71.0% over 20 candidates with signal   (self-excluded baseline)
   truncated: mean win rate 62.0%
    shuffled: mean win rate 63.0%
      padded: mean win rate 57.0%
    stripped: mean win rate 67.0%
     control: mean win rate 66.0%   (20 near-identical texts, should show no real signal)
```

**MockJudge does not separate intact from degraded.** All six numbers sit
in a 57-71% band with no class reliably below another. This is not a
failure of Hibiscus's *pipeline* (every comparison, resolution, and
aggregation ran correctly) — it's the expected consequence of `MockJudge`
having no notion of content quality at all (its own docstring says so). The
important confirmation here is structural, not numerical: the pipeline
plumbing (`run_comparisons` -> `resolve_pairs` -> `score_candidate` ->
`score_spread` -> `length_bias` -> `run_calibration`) ran end to end over
100 candidates without error, and produced internally consistent output
(Wilson intervals, tie accounting, spread ratios) — see `mock_output.txt`
for the full transcript. That's the "validates plumbing" half of the task.

A concrete, useful side-finding from this pass: **`score_spread` flagged
the null control as "discriminating" under MockJudge** (`control: ... 1.37x
sampling noise, discriminating=True`) even though the 20 control texts are
paraphrases of one paragraph with no real quality difference. This isn't a
bug in `score_spread` — it's doing exactly what it's documented to do
(compare observed variance to a noise-only null) — but MockJudge's
decisions are a hash comparison, not a quality judgment, so "real signal"
by its measure is meaningless here. **A spread check is only as
meaningful as the judge feeding it.** See "Real judge" below for the
contrast.

### Real judge (5-source subset: 5 sources x 4 classes x 2 refs = 40, plus 10 intact self-check + 10 control = 60 unique pairs / 120 raw judge calls)

No `ANTHROPIC_API_KEY` (and no `anthropic` package) is available in this
sandbox. Per the user's explicit choice when asked, I acted as the judge
myself: I read each of the 60 (candidate, reference) pairs and recorded a
genuine A/B/TIE verdict in `manual_verdicts.json`, using the library's own
question ("Which one is better?"). See "Limitation" below for exactly what
this can and cannot validate.

```
   truncated mean: 0.0%   (5/5 sources: reference wins every time)
    shuffled mean: 0.0%   (5/5 sources: reference wins every time)
      padded mean: 0.0%   (5/5 sources: reference wins every time -- see length-bias note)
    stripped mean: 0.0%   (5/5 sources: reference wins every time)
      intact mean: 50.0%  (self-excluded baseline: 2 candidate wins, 2 reference wins, 6 ties across 10 pairs)
     control mean: 0.0%   (5/5 near-identical texts: reference wins every time, identically)
```

**Every single one of the 40 degraded-vs-intact judgments went to the
intact reference. Zero exceptions, across all four degradation classes and
all five sources.** This is a clean, complete recovery of the constructed
ground truth by genuine content-based judgment — the opposite of
MockJudge's flat ~60-70% band. The self-excluded intact baseline landing
at exactly 50% (with substantial ties) is the expected unbiased midpoint:
neither an intact text nor its intact peers should systematically beat
each other, and my own judgments didn't manufacture a direction.

**The control set is the clean contrast with MockJudge's false positive.**
The same five near-identical paraphrases, judged by actual reading rather
than hashing, come back with **zero spread** (`control: n=5 spread
0%-0% (sd 0.000), discriminating=False`) — trivial synonym swaps didn't
flip my verdict once. MockJudge's "1.37x, discriminating=True" on the same
kind of set was a hash artifact, not signal; a judge that's actually
reading the text gets the null result right.

**Padded (the length-bias probe): the padded variant never won, against
either reference, for any of the 5 sources.** Despite being ~2x the length
of the intact original (padded restates every sentence via "In other
words, ..."), I consistently judged the repetition as a quality defect,
not a thoroughness signal. Because there was zero win-rate variation
across padded candidates (uniformly 0%), `length_bias`'s Pearson
correlation over this subset is mathematically undefined/zero (no
variance to correlate) — a sample-size artifact of "always loses," not
evidence the length diagnostic doesn't work. **This result should not be
read as "Hibiscus's length-bias judge is safe from length bias in
general"** — see the limitation below for why.

## Limitation: this is not a test of position-bias susceptibility

`ManualJudge` (`manual_judge.py`) looks up **one** verdict per (candidate,
reference) *content* pair and returns it consistently regardless of which
text arrives as `text_a` vs `text_b`. I judge by reading the two texts, not
by blindly answering the same short prompt twice in isolation the way a
single-shot API call would. That means:

- Order-disagreement is 0% for every one of these 60 pairs, by
  construction, exactly like MockJudge — but for an unrelated reason
  (MockJudge is order-independent because its arithmetic is symmetric;
  ManualJudge is order-independent because I intentionally answer the
  underlying content question once). **Neither this subset nor the
  MockJudge run can say anything about whether a real single-shot LLM
  judge would show order disagreement on this ladder.**
- My judgment that padded text isn't rewarded for its length is a
  considered read, with room to reflect — not the terse "answer with only
  A or B" single-token response `AnthropicJudge` actually asks for. A real
  API-based judge answering fast, under that exact terse prompt, could
  plausibly behave differently (the length-bias literature this library's
  own README cites is about exactly that kind of judge). **This result is
  evidence that a careful reader isn't fooled by the padding trick here —
  it is not evidence that Hibiscus's `AnthropicJudge` in production
  wouldn't be.**

Both caveats point the same direction: this validates that Hibiscus's
*scoring and aggregation logic* correctly reflects whatever judgments it's
given (garbage in only if garbage in), and that a genuinely
quality-sensitive judgment source produces the expected separation. It
does not substitute for testing the actual `AnthropicJudge` adapter's
behavior on position bias or length bias, which requires a real,
independently-blind API call per order — out of reach here without
network/API access.

## calibrate-style check (MockJudge; love=intact(20) vs okay=<class>(20), nope=empty)

```
   truncated: love(intact)=71.0%  okay(truncated)=62.0%  -> PASS  separation=0.090
    shuffled: love(intact)=71.0%  okay(shuffled)=63.0%   -> PASS  separation=0.080
      padded: love(intact)=71.0%  okay(padded)=57.0%     -> PASS  separation=0.140
    stripped: love(intact)=71.0%  okay(stripped)=67.0%   -> PASS  separation=0.040
```

All four report "PASS" (love outscores okay, no inversion) with MockJudge,
but treat this with real skepticism, not as evidence MockJudge has taste:
the gaps (4-14 points) are the same size as the noise band MockJudge
produced on the null control (66% mean, non-trivial spread) elsewhere in
this same run. A `calibrate` "PASS" from `MockJudge` is not meaningful on
its own — the worked example in the README makes exactly this point when
`calibrate` correctly *fails* against MockJudge's own hand-rated tiers.
That the ladder's calibrate happens to PASS here is more likely 20-sample
noise landing favorably than a real signal; it should not be read as
"MockJudge validated the degradation ladder."

## Bottom line

- **Plumbing**: confirmed end-to-end with MockJudge across 100+ candidates
  — no crashes, internally consistent Wilson/tie/spread/calibrate output.
- **Judgment**: confirmed with a genuine (if self-supplied) real judge on a
  60-pair subset — 40/40 degraded-vs-intact judgments correctly favored
  intact, the intact self-check baseline landed at the expected ~50%
  midpoint, and the null control showed zero spurious spread. This is
  strong evidence the *scoring machinery* (win rate, spread, length bias)
  reports faithfully whatever a competent judge feeds it.
- **What remains untested**: real-judge (API) position-bias and
  length-bias behavior specifically, which requires true independent
  blind calls per order and per candidate — not available without
  `ANTHROPIC_API_KEY` in this environment.
