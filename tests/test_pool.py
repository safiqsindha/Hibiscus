from __future__ import annotations

import pytest

from hibiscus import Pool, RatedArtifact, Tier


def test_add_and_filter_by_tier(tmp_path):
    pool = Pool(tmp_path / "pool.jsonl")
    pool.add(RatedArtifact(id="a1", text="hello", tier=Tier.LOVE))
    pool.add(RatedArtifact(id="a2", text="world", tier=Tier.OKAY))

    assert len(pool) == 2
    assert [r.id for r in pool.filter_by_tier(Tier.LOVE)] == ["a1"]
    assert [r.id for r in pool.filter_by_tier("okay")] == ["a2"]


def test_duplicate_rating_rejected_unless_overwrite(tmp_path):
    pool = Pool(tmp_path / "pool.jsonl")
    pool.add(RatedArtifact(id="a1", text="hello", tier=Tier.LOVE))

    with pytest.raises(ValueError):
        pool.add(RatedArtifact(id="a1", text="hello2", tier=Tier.OKAY))

    pool.add(RatedArtifact(id="a1", text="hello2", tier=Tier.OKAY), overwrite=True)
    assert pool.get("a1").tier is Tier.OKAY


def test_persists_and_reloads_across_instances(tmp_path):
    path = tmp_path / "pool.jsonl"
    Pool(path).add(RatedArtifact(id="a1", text="hello", tier=Tier.LOVE))

    reloaded = Pool(path)
    assert "a1" in reloaded
    assert reloaded.get("a1").tier is Tier.LOVE
    assert reloaded.get("missing") is None


def test_utf8_round_trip_on_special_characters(tmp_path):
    text = "middot · en–dash em—dash “curly” non breaking café"
    path = tmp_path / "pool.jsonl"
    Pool(path).add(RatedArtifact(id="u1", text=text, tier=Tier.NOPE))

    reloaded = Pool(path)
    assert reloaded.get("u1").text == text
    raw = path.read_text(encoding="utf-8")
    assert "\\u" not in raw


def test_export_and_import_round_trip(tmp_path):
    pool = Pool(tmp_path / "pool.jsonl")
    pool.add(RatedArtifact(id="a1", text="x", tier=Tier.LOVE, note="great"))

    export_path = tmp_path / "export.jsonl"
    pool.export_jsonl(export_path)

    pool2 = Pool(tmp_path / "pool2.jsonl")
    count = pool2.import_jsonl(export_path)

    assert count == 1
    assert pool2.get("a1").note == "great"


def test_list_is_sorted_and_filterable(tmp_path):
    pool = Pool(tmp_path / "pool.jsonl")
    pool.add(RatedArtifact(id="b", text="x", tier=Tier.LOVE))
    pool.add(RatedArtifact(id="a", text="x", tier=Tier.NOPE))

    assert [r.id for r in pool.list()] == ["a", "b"]
    assert [r.id for r in pool.list(tier=Tier.LOVE)] == ["b"]
