# 3. Wikipedia quality classes — blocked by environment network policy

**Script:** `check_access.py` (documents the block; does not perform the
validation). Raw output: `check_access_output.txt`. No library code was
touched, and no Wikipedia data was fetched.

## Status: not completed

This validation could not be run in this sandbox. `en.wikipedia.org`,
`wikimedia.org`, and `dumps.wikimedia.org` are all rejected at the network
egress proxy with `403 (policy denial)` — not a transient failure, and not
something to route around (per this environment's own guidance: *"do not
retry organization policy denials ... report them instead"*). The proxy's
`recentRelayFailures` log confirms the same for every mirror/alternative
I checked: `huggingface.co`, `commoncrawl.org`, `simple.wikipedia.org`,
`www.gutenberg.org`, `arxiv.org`. The `WebFetch` tool hits the identical
policy wall (`EGRESS_BLOCKED: en.wikipedia.org`), so this isn't a curl/TLS
issue — it's the same organization-level allowlist regardless of tool.

What *is* reachable from this sandbox, confirmed while running validations
1 and 2: GitHub (`github.com`, `raw.githubusercontent.com`, and the
scoped `add_repo`/clone flow) and `storage.googleapis.com`. The egress
policy here appears to be a narrow allowlist (GitHub, package registries
like PyPI/npm, Google Cloud Storage, the Anthropic API) rather than a
Wikipedia-specific block.

## What I did not do

I deliberately did not substitute a different, less-authoritative
"Wikipedia-quality-like" dataset without checking with you first, and did
not spend effort guessing at possibly-hallucinated GitHub mirror URLs for
Wikipedia FA/GA/B/C/Start/Stub article *text* (as opposed to just labels
+ revision IDs, which some GitHub-hosted research repos — e.g.
`wikimedia/articlequality` — do carry, but reconstructing full article
prose from a revision ID still requires hitting `en.wikipedia.org`, which
is the blocked step). Guessing at a specific dataset repo I'm not certain
exists risks either wasting a clone on the wrong thing or silently
lowering the bar for what counts as "a third party's hand-rated tier
system" without flagging that substitution.

## Options, if you want this validation completed

1. **Run it in an environment with broader network access** (e.g. your
   own machine, or a Claude Code session/environment whose egress policy
   allows `en.wikipedia.org`) — the MediaWiki API itself is simple
   (`action=query&prop=extracts`, plus `action=query&list=categorymembers`
   for pulling articles by quality-assessment category), and the rest of
   this validation's harness (pool construction, `calibrate`, win-rate
   scoring) is already written and tested in `../01_synthetic_ladder/` and
   can be adapted directly once article text is available.
2. **Point me at a specific, already-known dataset** you trust that
   packages Wikipedia quality-graded article *text* (not just labels), if
   one is reachable from GitHub/GCS/PyPI — I'll use it instead of the live
   API.
3. **Skip this validation** and treat 0/1/2 as the external evidence for
   this round; note in the top-level summary that the third-party
   hand-rated check remains open.

I'd lean toward (1) or (3) rather than guessing at a substitute source,
but this is your call.
