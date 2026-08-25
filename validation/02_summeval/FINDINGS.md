# 2. SummEval correlation check

**Script:** `run_summeval.py`. Raw output: `summeval_output.txt`,
`summeval_results.json`. Data: `data/model_annotations.aligned.jsonl`
(real SummEval human annotations, downloaded directly from
`storage.googleapis.com/sfr-summarization-repo-research/...`, the canonical
URL published in the Yale-LILY/SummEval GitHub README). No library code
was changed. Zero judge/API spend.

## Data

100 source articles x 16 summarization systems = 1,600 summaries, each
independently rated by 3 expert annotators on four dimensions (coherence,
consistency, fluency, relevance), scale 1-5. Per Hibiscus's expected input
shape, each summary is one `artifact_id` (`{article_id}__{model_id}`), and
its per-dimension score is the mean of the 3 expert ratings on that
dimension — 6,400 `{artifact_id, dimension, score}` rows total.

## `hibiscus report` output (default threshold 0.85)

```
              coherence  consistency  fluency  relevance
   coherence     1.0000       0.3151   0.3844     0.6598
 consistency     0.3151       1.0000   0.4884     0.4125
     fluency     0.3844       0.4884   1.0000     0.3696
   relevance     0.6598       0.4125   0.3696     1.0000

redundant pairs (>= 0.85): none
```

Ranked: coherence<->relevance is clearly the strongest pair (0.66), then
consistency<->fluency (0.49), consistency<->relevance (0.41),
coherence<->fluency (0.38), fluency<->relevance (0.37), and
coherence<->consistency is the weakest (0.32).

## Cross-check against an independent implementation

Recomputed the identical dimension x dimension matrix with `scipy.stats.pearsonr`
/ `numpy`, over the same shared-artifact basis `build_correlation_report`
uses (pairwise intersection, not a single global intersection across all
four dimensions). **Max absolute difference across every matrix cell:
`0.0000000000`.** Hibiscus's `pearson()` (`src/hibiscus/report.py`) is
exactly correct on real, non-synthetic data at this scale (6,400 rows) —
this isn't just a formula that happens to work on the library's own
toy-sized unit-test fixtures.

## Does this match published SummEval numbers?

I could not fetch the SummEval paper (`arxiv.org`) or the GitHub issue
thread with community-computed correlations to check against a specific
published figure — this sandbox's network egress policy blocks
`arxiv.org` outright (only GitHub, PyPI/npm/etc., and Google Cloud Storage
are reachable; see `../03_wikipedia/FINDINGS.md`). What I can say
confidently: the *shape* of the result is unsurprising and directionally
sane for anyone familiar with the SummEval dimensions — coherence and
relevance are the most conceptually overlapping pair of the four (a
summary that pulls the right content also tends to read as well-organized
around it), and that pair is indeed the strongest correlation found, well
above the rest. None of the six pairs are anywhere near 0.85, so this
specific dataset, at this granularity (per-summary, expert-mean scores),
is **not** an example of the "0.85-0.95, measuring the same thing five
times" failure mode the README describes from the unrelated project that
motivated this library. That's a fair result to report honestly, not a
disappointment: it demonstrates the diagnostic runs correctly and returns
"nothing flagged" when nothing *should* be flagged, at least at this
default threshold and this level of aggregation.

## A caveat worth flagging: the choice of aggregation changes the answer

This reshaping averaged the 3 expert scores per summary per dimension
before correlating. That's a defensible default and matches what
`hibiscus report`'s input contract expects (one score per artifact per
dimension) — but it is a choice. Correlating one specific annotator's raw
scores instead (rather than the 3-way mean) would very likely raise
apparent correlation between dimensions, since averaging over 3 raters
already cancels some of each individual annotator's idiosyncratic
rating noise. This isn't a bug in `hibiscus report` — the tool has no way
to know it's being fed pre-averaged data versus raw per-rater data — but
it means the "0.85 default threshold" carries an implicit assumption
about how granular the input scores are. Feeding it single-annotator
scores instead of averages, or system-level means instead of per-summary
scores, would likely shift every correlation and could plausibly push
some pairs at or above 0.85. Worth a note in the README if it isn't
already there: the threshold is calibrated against *some* granularity of
input, and that granularity should probably be stated as an assumption
(e.g. "one score per artifact per dimension, not pre-averaged over
independent raters, and not itself a mean over many artifacts").
