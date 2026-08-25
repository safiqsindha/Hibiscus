from __future__ import annotations

import json

import pytest

from hibiscus import Artifact, Pool, RatedArtifact, Tier
from hibiscus.compare import run_comparisons
from hibiscus.judge.base import JudgeAdapter, JudgeVerdict
from hibiscus.judge.payload import ALLOWED_PAYLOAD_KEYS, build_judge_payload, validate_payload


def test_payload_contains_only_whitelisted_keys():
    payload = build_judge_payload("text A", "text B", "which is better?")
    assert set(payload.keys()) == ALLOWED_PAYLOAD_KEYS == {"text_a", "text_b", "question"}


def test_validate_payload_rejects_disallowed_keys():
    poisoned = {
        "text_a": "a",
        "text_b": "b",
        "question": "q",
        "candidate_id": "c1",  # must never reach the judge
        "tier": "love",
    }
    with pytest.raises(AssertionError):
        validate_payload(poisoned)


def test_validate_payload_accepts_clean_payload():
    validate_payload({"text_a": "a", "text_b": "b", "question": "q"})  # should not raise


def test_run_comparisons_never_leaks_ids_tiers_or_metadata(tmp_path):
    seen_payloads = []

    class RecordingJudge(JudgeAdapter):
        def compare(self, text_a, text_b, question):
            seen_payloads.append({"text_a": text_a, "text_b": text_b, "question": question})
            return JudgeVerdict(winner="a", raw_response="mock:a")

    pool = Pool(tmp_path / "pool.jsonl")
    pool.add(
        RatedArtifact(
            id="SECRET-REF-ID",
            text="a reference artifact",
            tier=Tier.LOVE,
            metadata={"source": "internal-only"},
        )
    )
    candidate = Artifact(
        id="SECRET-CANDIDATE-ID", text="a candidate artifact", metadata={"owner": "alice"}
    )

    run_comparisons(candidate, pool, RecordingJudge(), k=1, seed=0, model="test")

    assert seen_payloads, "the recording judge should have been called"
    for payload in seen_payloads:
        assert set(payload.keys()) == {"text_a", "text_b", "question"}
        blob = json.dumps(payload)
        assert "SECRET-REF-ID" not in blob
        assert "SECRET-CANDIDATE-ID" not in blob
        assert "love" not in blob
        assert "internal-only" not in blob
        assert "alice" not in blob
