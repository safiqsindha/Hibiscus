# Hibiscus

Hibiscus judges generated artifacts the way a jury does: not with a score
out of five, but by hanging each candidate next to accepted work and asking
which is better. Rate your candidates into tiers, keep the best as the hung
set, and score everything after by how often it wins.

## Why not just score things 0–10?

Absolute rubric scoring fails in a specific, documented way. In a comparable
project — [reinforcement learning for generative art](https://surya.website/rling-qwen-to-paint-with-code) —
a nine-signal absolute rubric plateaued, and every output converged to look
identical. The diagnosis: five of the nine judges correlated at 0.85–0.95
with each other — measuring the same thing five times — while the one
signal with real variance carried only 10% of the weight. Absolute 0–10
scores came back compressed near zero, with no room for the judge to
express a preference.

Two fixes worked there, and Hibiscus packages both:

1. **Pairwise judgment.** Show the judge the candidate plus references
   sampled from a rated pool and ask which is better. Reward becomes the
   fraction of comparisons won. Dynamic range opens up, because judges are
   measurably more reliable at relative questions ("which is better?") than
   at absolute ones ("rate this 0–10").
2. **A hand-rated reference pool.** 1,664 candidates were rated one at a
   time into love / okay / nope; the 117 love-tier examples became the
   comparison set. Notably, human-made references weren't available for
   that project's niche medium — the entire pool was model output that a
   human rated. Hibiscus assumes the same by default: **the pool is
   curated taste, not ground truth.**

Hibiscus also ships the diagnostic that found the original problem: a
dimension-correlation report you can point at any set of scores — its own
output or an existing rubric's history — to catch redundant judges before
they quietly dominate a weighted average.

## Core concepts

| Concept        | Meaning |
|-----------------|---------|
| **Artifact**    | Any text blob with an id and optional metadata. Domain-agnostic — prose, code, docs, synthetic data. |
| **Tier**        | `love` / `okay` / `nope`. Exactly three, ordered. `love` is the "hung set" used as comparison foils. |
| **Pool**        | The rated collection, one artifact kind per pool. Multiple named pools are just multiple files. |
| **Comparison**  | One judge call: candidate vs. one reference, run in both orders to control for position bias. |
| **Win rate**    | Fraction of comparisons won, reported with a Wilson score confidence interval. |

## Install

```bash
pip install -e .            # core library + CLI
pip install -e ".[anthropic]"  # + the Anthropic judge adapter
pip install -e ".[dev]"        # + test dependencies
```

Requires Python 3.10+. No dependencies beyond the standard library unless
you use the Anthropic adapter.

## Quickstart (CLI)

```bash
# 1. Rate a batch of candidates into love/okay/nope. One keystroke per item
#    (SHIFT+key to add a note), resumable — quitting and rerunning skips
#    anything already rated.
hibiscus rate --artifacts candidates.jsonl --pool pools/my-pool.jsonl

# 2. Compare new candidates against the love tier (k=2 references, both
#    orders, seeded for reproducibility).
hibiscus compare \
  --candidates new_candidates.jsonl \
  --pool pools/my-pool.jsonl \
  --seed 42 \
  --judge anthropic --model claude-sonnet-5 \
  --cache cache/judge_cache.jsonl \
  --out comparisons.jsonl

# 3. Turn comparisons into win rates with confidence intervals.
hibiscus score --comparisons comparisons.jsonl --out scores.json

# 4. Run the correlation diagnostic on any {artifact_id, dimension, score}
#    data — Hibiscus's own or an existing rubric's history.
hibiscus report --data existing_rubric_scores.csv --threshold 0.85
```

`--judge mock` (the default) uses a deterministic, offline judge — useful
for dry-running a pipeline without an API key. See [`examples/worked_example.py`](examples/worked_example.py)
for a full run using it.

### `hibiscus pool`

```bash
hibiscus pool add --pool pools/my-pool.jsonl --id ex-042 --text-file ex-042.txt --tier love --note "clean structure"
hibiscus pool list --pool pools/my-pool.jsonl --tier love
hibiscus pool export --pool pools/my-pool.jsonl --out backup.jsonl
hibiscus pool import --pool pools/my-pool.jsonl --src backup.jsonl
```

Artifact and rating files are UTF-8 JSONL, one object per line:

```json
{"id": "ex-042", "text": "...", "metadata": {"kind": "meeting-notes"}}
```

## Python API

```python
from hibiscus import Artifact, Pool, RatedArtifact, Tier
from hibiscus.compare import run_comparisons, order_disagreement_rate
from hibiscus.judge.mock import MockJudge
from hibiscus.score import score_candidate

pool = Pool("pools/my-pool.jsonl")
pool.add(RatedArtifact(id="ref-1", text="a reference worth citing", tier=Tier.LOVE))

candidate = Artifact(id="cand-1", text="the new thing to judge")
records = run_comparisons(candidate, pool, MockJudge(), k=2, seed=42, model="mock-v1")

print(order_disagreement_rate(records))          # judge-reliability signal
print(score_candidate(records, candidate_id="cand-1"))  # WinRateResult
```

## Components

1. **`rate`** — human rating CLI. One artifact at a time; `l`/`o`/`n`
   records the rating and advances immediately — no Enter, no
   confirmation. Shift the key (`L`/`O`/`N`) to attach a free-text note
   to that rating. Resumable, and never re-presents an already-rated
   item.
2. **`pool`** — storage and query. Add, list, filter by tier, export/import
   JSONL. Explicit UTF-8 on every read and write, always.
3. **`compare`** — samples K references from a chosen tier (default:
   `love`, K=2), runs the pairwise judge, and controls for position bias by
   running every comparison in both orders. Surfaces the order-disagreement
   rate as a judge-reliability signal: if the judge's answer flips with
   position, it isn't discriminating on content.
4. **`score`** — aggregates comparisons into a win rate with a Wilson score
   confidence interval. Supports per-dimension scoring when comparisons
   carry a `dimension`, but a single overall judgment is the default and
   the recommended path.
5. **`report`** — the correlation diagnostic. Given any set of artifacts
   scored on multiple dimensions (CSV or JSONL of
   `{artifact_id, dimension, score}`), outputs a correlation matrix and
   flags pairs above a threshold (default 0.85) as redundant. Works on
   externally-produced score data, not just Hibiscus's own.

## Judge interface

Judges are pluggable via `hibiscus.judge.base.JudgeAdapter`:

```python
class JudgeAdapter(ABC):
    def compare(self, text_a: str, text_b: str, question: str) -> JudgeVerdict:
        ...
```

The judge receives **only** `text_a`, `text_b`, and `question` — never an
artifact id, tier label, or pool metadata. This is enforced by
`hibiscus.judge.payload.build_judge_payload`, which whitelists the payload
by construction and asserts on it before any call is made, so a leak fails
the build, not the judge call.

Two adapters ship in the box:

- `hibiscus.judge.mock.MockJudge` — deterministic, offline, hash-based.
  Good for pipeline smoke tests.
- `hibiscus.judge.anthropic_adapter.AnthropicJudge` — calls a Claude model.
  Requires `pip install hibiscus[anthropic]` and `ANTHROPIC_API_KEY`
  (or pass `api_key=`).

The default comparison question is deliberately short:

> Below are two texts, A and B. Which one is better? Answer with only the
> single letter A or B.

A long rubric in the prompt measurably hurt judgment quality in the project
this library is based on — a 400-line API reference in a system prompt
made a model hallucinate, while a short, opinionated allowlist outperformed
the full spec. Override the question per-call (`--question` / `question=`)
if you need to steer it, but keep it short.

## Determinism and reproducibility

- Reference sampling is seeded (`random.Random(seed)`); the same seed
  against the same pool always samples the same references.
- Every comparison is logged: candidate id, reference id, order, judge
  response, timestamp, model id, and a hash of the comparison prompt.
- Judge calls default to temperature 0 (configurable on the adapter).
- Judge responses are cached, keyed on `(candidate hash, reference hash,
  order, prompt hash, model)` — identical inputs never re-hit the judge, so
  reruns are free and byte-for-byte reproducible.

## Non-goals

Hibiscus does not generate artifacts, fine-tune models, train reward
models, or assume any domain-specific document schema. It judges text you
already have.

## Testing

```bash
pip install -e ".[dev]"
pytest
```

The full suite runs without network access — the Anthropic adapter is
never exercised directly; a mock/fake `JudgeAdapter` stands in everywhere
comparisons need a judge.

## Worked example

```bash
pip install -e .
python examples/worked_example.py
```

Builds a five-item love-tier pool, compares a strong and a weak candidate
against it with `MockJudge`, prints win rates with Wilson intervals and the
order-disagreement rate, then runs the correlation diagnostic on synthetic
dimension scores that include a deliberately duplicated signal — the same
kind of redundancy that motivated this library.

## License

MIT — see [LICENSE](LICENSE).
