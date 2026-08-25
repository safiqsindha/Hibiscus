from __future__ import annotations

import io

from hibiscus import Artifact, Pool, Tier
from hibiscus.cli.rate import run_rate_session


def make_reader(keys):
    it = iter(keys)
    return lambda: next(it)


def no_note():
    return ""


def test_resume_never_double_presents(tmp_path):
    artifacts = [Artifact(id=f"a{i}", text=f"text {i}") for i in range(3)]
    pool_path = tmp_path / "pool.jsonl"

    pool = Pool(pool_path)
    run_rate_session(
        artifacts[:2],
        pool,
        read_key=make_reader(["l", "o"]),
        read_note=no_note,
        out=io.StringIO(),
    )
    assert pool.get("a0").tier is Tier.LOVE
    assert pool.get("a1").tier is Tier.OKAY

    # Resume with a fresh Pool instance over the full artifact list: the
    # already-rated a0/a1 must not reappear, only a2 gets prompted.
    pool2 = Pool(pool_path)
    out = io.StringIO()
    run_rate_session(
        artifacts, pool2, read_key=make_reader(["n"]), read_note=no_note, out=out
    )

    assert pool2.get("a2").tier is Tier.NOPE
    transcript = out.getvalue()
    assert "text 0" not in transcript
    assert "text 1" not in transcript
    assert "text 2" in transcript


def test_ratings_persist_across_restart(tmp_path):
    pool_path = tmp_path / "pool.jsonl"
    artifacts = [Artifact(id="a0", text="t0")]

    run_rate_session(
        artifacts, Pool(pool_path), read_key=make_reader(["l"]), read_note=no_note, out=io.StringIO()
    )

    restarted = Pool(pool_path)
    assert restarted.get("a0").tier is Tier.LOVE


def test_quit_stops_without_rating_remaining(tmp_path):
    artifacts = [Artifact(id="a0", text="t0"), Artifact(id="a1", text="t1")]
    pool = Pool(tmp_path / "pool.jsonl")

    run_rate_session(artifacts, pool, read_key=make_reader(["q"]), read_note=no_note, out=io.StringIO())

    assert len(pool) == 0


def test_skip_moves_to_next_without_rating(tmp_path):
    artifacts = [Artifact(id="a0", text="t0"), Artifact(id="a1", text="t1")]
    pool = Pool(tmp_path / "pool.jsonl")

    run_rate_session(
        artifacts, pool, read_key=make_reader(["s", "l"]), read_note=no_note, out=io.StringIO()
    )

    assert "a0" not in pool
    assert pool.get("a1").tier is Tier.LOVE


def test_invalid_keystroke_reprompts(tmp_path):
    artifacts = [Artifact(id="a0", text="t0")]
    pool = Pool(tmp_path / "pool.jsonl")

    run_rate_session(
        artifacts, pool, read_key=make_reader(["x", "z", "l"]), read_note=no_note, out=io.StringIO()
    )

    assert pool.get("a0").tier is Tier.LOVE


def test_note_is_recorded(tmp_path):
    artifacts = [Artifact(id="a0", text="t0")]
    pool = Pool(tmp_path / "pool.jsonl")

    run_rate_session(
        artifacts,
        pool,
        read_key=make_reader(["l"]),
        read_note=lambda: "reminds me of early Ashbery",
        out=io.StringIO(),
    )

    assert pool.get("a0").note == "reminds me of early Ashbery"


def test_utf8_round_trip_through_rate_session(tmp_path):
    text = "middot · en–dash em—dash “curly” non breaking café"
    artifacts = [Artifact(id="u1", text=text)]
    pool_path = tmp_path / "pool.jsonl"

    run_rate_session(
        artifacts, Pool(pool_path), read_key=make_reader(["l"]), read_note=no_note, out=io.StringIO()
    )

    reloaded = Pool(pool_path)
    assert reloaded.get("u1").text == text
