from __future__ import annotations

import importlib.util
import json
import os
import struct
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "lib_lens_registry.py"
EMBED_DIM = 768


@pytest.fixture
def lens_registry():
    if not MODULE_PATH.exists():
        pytest.skip("scripts/lib_lens_registry.py has not been implemented")
    spec = importlib.util.spec_from_file_location("lib_lens_registry_under_test", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_lens_registry_module_exists():
    assert MODULE_PATH.exists(), "scripts/lib_lens_registry.py has not been implemented"


def _unit_vector(index: int) -> list[float]:
    vector = [0.0] * EMBED_DIM
    vector[index] = 1.0
    return vector


def _write_registry(root: Path) -> list[dict]:
    generated = root / "data" / "generated"
    lenses = generated / "lenses"
    specs = generated / "specs"
    embeddings = root / "data" / "embeddings"
    lenses.mkdir(parents=True)
    specs.mkdir(parents=True)
    embeddings.mkdir(parents=True)

    records = [
        {
            "id": "gen:fd-canonical@aaaaaaaa",
            "name": "fd-canonical",
            "summary": "identity migration boundary cutover",
            "cluster": {"head": True, "id": "cluster-a"},
            "cohort": {"siblings": ["fd-canonical", "fd-neighbor"]},
            "corrupt": True,
            "body_path": "generated/lenses/gen:fd-canonical@aaaaaaaa.md",
            "spec_path": "generated/specs/gen:fd-canonical@aaaaaaaa.json",
            "stats": {"hit_rate": 0.75},
            "embodies": [{"id": "lens_1", "score": 0.7}],
        },
        {
            "id": "gen:fd-body-only@bbbbbbbb",
            "name": "fd-body-only",
            "summary": "queue fairness backpressure",
            "cluster": {"head": True, "id": None},
            "cohort": {"siblings": ["fd-body-only"]},
            "corrupt": False,
            "body_path": "generated/lenses/gen:fd-body-only@bbbbbbbb.md",
            "spec_path": None,
            "stats": {"hit_rate": None},
            "embodies": [],
        },
        {
            "id": "gen:fd-variant@cccccccc",
            "name": "fd-variant",
            "summary": "identity migration boundary cutover",
            "cluster": {"head": False, "id": "cluster-a"},
            "corrupt": False,
            "body_path": "generated/lenses/gen:fd-variant@cccccccc.md",
            "spec_path": None,
        },
        {
            "id": "gen:fd-corrupt-no-spec@dddddddd",
            "name": "fd-corrupt-no-spec",
            "summary": "identity migration boundary cutover",
            "cluster": {"head": True, "id": None},
            "corrupt": True,
            "body_path": "generated/lenses/gen:fd-corrupt-no-spec@dddddddd.md",
            "spec_path": None,
        },
    ]
    (generated / "index.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in records), encoding="utf-8"
    )
    (specs / "gen:fd-canonical@aaaaaaaa.json").write_text(
        json.dumps(
            {
                "name": "fd-canonical",
                "focus": "Identity migration boundary cutover.",
                "persona": "Registry persona with clean source material.",
                "decision_lens": "Prefer reversible transitions.",
                "review_areas": ["Check cutover boundaries and rollback."],
                "severity_examples": [
                    {
                        "severity": "P1",
                        "scenario": "A cutover strands active identities",
                        "condition": "The rollback boundary has already moved",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (lenses / "gen:fd-canonical@aaaaaaaa.md").write_text(
        "---\nname: fd-canonical\ndescription: stale body\n---\n[truncated — 99 chars omitted]\n",
        encoding="utf-8",
    )
    (lenses / "gen:fd-body-only@bbbbbbbb.md").write_text(
        "---\nname: fd-body-only\ndescription: Queue specialist\ntier: generated\n---\n"
        "# Body-only lens\n\nKeep this body verbatim.\n",
        encoding="utf-8",
    )

    ids = [records[0]["id"], records[1]["id"], records[2]["id"], records[3]["id"]]
    (embeddings / "generated.ids.json").write_text(json.dumps(ids), encoding="utf-8")
    vectors = [_unit_vector(0), _unit_vector(1), _unit_vector(2), _unit_vector(3)]
    (embeddings / "generated.f32").write_bytes(
        b"".join(struct.pack(f"<{EMBED_DIM}f", *vector) for vector in vectors)
    )
    (embeddings / "meta.json").write_text(
        json.dumps({"model": "nomic-embed-text", "dim": EMBED_DIM}), encoding="utf-8"
    )
    return records


@contextmanager
def _fake_ollama(vector: list[float]):
    requests: list[dict] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802 - BaseHTTPRequestHandler API
            length = int(self.headers.get("content-length", "0"))
            payload = json.loads(self.rfile.read(length))
            requests.append(payload)
            response = json.dumps({"embeddings": [vector for _ in payload["input"]]}).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _frontmatter(text: str) -> dict:
    assert text.startswith("---\n")
    end = text.index("\n---\n", 4)
    return yaml.safe_load(text[4:end])


def test_embedding_text_matches_harvest_recipe(lens_registry):
    spec = {
        "persona": "A migration operator",
        "focus": "Identity boundaries",
        "decision_lens": "Prefer reversible cuts",
        "review_areas": ["Check rollback", "Check propagation"],
    }
    assert lens_registry.embedding_text(spec, "ignored") == (
        "A migration operator\nIdentity boundaries\nPrefer reversible cuts\n"
        "Check rollback\nCheck propagation"
    )

    body = (
        "Apply the perspective of a queue operator.\n\n"
        "### 1. Backpressure\n\nDetails.\n\n### 2. Fairness\n"
    )
    assert lens_registry.embedding_text(None, body) == (
        "Apply the perspective of a queue operator.\n"
        "Backpressure\nFairness\n"
        "Apply the perspective of a queue operator. ### 1. Backpressure Details. ### 2. Fairness"
    )


def test_find_registry_root_and_load_only_cluster_heads(tmp_path, monkeypatch, lens_registry):
    root = tmp_path / "registry"
    _write_registry(root)
    monkeypatch.setenv("LINSENKASTEN_ROOT", str(root))

    assert lens_registry.find_registry_root() == root
    assert [record["name"] for record in lens_registry.load()] == [
        "fd-canonical",
        "fd-body-only",
        "fd-corrupt-no-spec",
    ]


def test_find_registry_root_returns_none_without_an_index(tmp_path, monkeypatch, lens_registry):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("LINSENKASTEN_ROOT", str(tmp_path / "empty"))
    (tmp_path / "empty").mkdir()

    assert lens_registry.find_registry_root() is None


def test_find_registry_root_uses_newest_cached_plugin(tmp_path, monkeypatch, lens_registry):
    home = tmp_path / "home"
    older = home / ".claude" / "plugins" / "cache" / "interagency-marketplace" / "linsenkasten" / "2.9.0"
    newer = home / ".claude" / "plugins" / "cache" / "interagency-marketplace" / "linsenkasten" / "3.0.0"
    _write_registry(older)
    _write_registry(newer)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("LINSENKASTEN_ROOT", raising=False)

    assert lens_registry.find_registry_root() == newer


def test_resolve_uses_local_then_fallback_ollama_and_generated_matrix(
    tmp_path, monkeypatch, lens_registry
):
    root = tmp_path / "registry"
    _write_registry(root)
    monkeypatch.setenv("LINSENKASTEN_ROOT", str(root))
    monkeypatch.setenv("LINSENKASTEN_OLLAMA_URL", "http://127.0.0.1:1")

    with _fake_ollama(_unit_vector(0)) as (url, requests):
        monkeypatch.setenv("LINSENKASTEN_OLLAMA_FALLBACK_URL", url)
        match = lens_registry.resolve(
            {"name": "fd-new", "focus": "Identity migration", "persona": "Operator"}
        )

    assert match is not None
    assert match["id"] == "gen:fd-canonical@aaaaaaaa"
    assert match["registry_id"] == match["id"]
    assert match["method"] == "embedding"
    assert match["embed_tier"] == "fallback"
    assert match["score"] == pytest.approx(1.0)
    assert requests == [
        {
            "model": "nomic-embed-text",
            "input": ["Operator\nIdentity migration"],
        }
    ]


def test_resolve_uses_local_ollama_and_ignores_non_heads(
    tmp_path, monkeypatch, lens_registry
):
    root = tmp_path / "registry"
    _write_registry(root)
    monkeypatch.setenv("LINSENKASTEN_ROOT", str(root))
    monkeypatch.setenv("LINSENKASTEN_OLLAMA_FALLBACK_URL", "http://127.0.0.1:1")

    with _fake_ollama(_unit_vector(2)) as (url, requests):
        monkeypatch.setenv("LINSENKASTEN_OLLAMA_URL", url)
        match = lens_registry.resolve(
            {"name": "fd-new", "focus": "Identity migration", "persona": "Operator"}
        )

    assert match is None
    assert len(requests) == 1


def test_resolve_uses_lexical_fallback_and_rejects_corrupt_body_without_spec(
    tmp_path, monkeypatch, lens_registry
):
    root = tmp_path / "registry"
    _write_registry(root)
    monkeypatch.setenv("LINSENKASTEN_ROOT", str(root))
    monkeypatch.setenv("LINSENKASTEN_OLLAMA_URL", "http://127.0.0.1:1")
    monkeypatch.delenv("LINSENKASTEN_OLLAMA_FALLBACK_URL", raising=False)

    exact = lens_registry.resolve({"name": "fd-body-only", "focus": "unrelated"})
    corrupt = lens_registry.resolve({"name": "fd-corrupt-no-spec", "focus": "unrelated"})

    assert exact is not None
    assert exact["id"] == "gen:fd-body-only@bbbbbbbb"
    assert exact["method"] == "lexical"
    assert exact["embed_tier"] == "lexical"
    assert exact["score"] == 1.0
    assert corrupt is None


def test_resolve_lexical_fallback_uses_focus_summary_jaccard(
    tmp_path, monkeypatch, lens_registry
):
    root = tmp_path / "registry"
    _write_registry(root)
    monkeypatch.setenv("LINSENKASTEN_ROOT", str(root))
    monkeypatch.setenv("LINSENKASTEN_OLLAMA_URL", "http://127.0.0.1:1")
    monkeypatch.delenv("LINSENKASTEN_OLLAMA_FALLBACK_URL", raising=False)

    match = lens_registry.resolve(
        {"name": "fd-new", "focus": "queue fairness backpressure"}
    )
    miss = lens_registry.resolve({"name": "fd-new", "focus": "queue latency"})

    assert match is not None
    assert match["id"] == "gen:fd-body-only@bbbbbbbb"
    assert match["method"] == "lexical"
    assert match["score"] == pytest.approx(1.0)
    assert miss is None


def test_resolve_empty_embedding_text_uses_lexical_without_ollama(
    tmp_path, monkeypatch, lens_registry
):
    root = tmp_path / "registry"
    _write_registry(root)
    monkeypatch.setenv("LINSENKASTEN_ROOT", str(root))
    monkeypatch.delenv("LINSENKASTEN_OLLAMA_FALLBACK_URL", raising=False)

    with _fake_ollama(_unit_vector(0)) as (url, requests):
        monkeypatch.setenv("LINSENKASTEN_OLLAMA_URL", url)
        match = lens_registry.resolve({"name": "fd-body-only"})

    assert match is not None
    assert match["id"] == "gen:fd-body-only@bbbbbbbb"
    assert match["method"] == "lexical"
    assert requests == []


def test_resolve_uses_lexical_when_embedding_matrix_is_missing(
    tmp_path, monkeypatch, lens_registry
):
    root = tmp_path / "registry"
    _write_registry(root)
    (root / "data" / "embeddings" / "generated.f32").unlink()
    monkeypatch.setenv("LINSENKASTEN_ROOT", str(root))
    monkeypatch.delenv("LINSENKASTEN_OLLAMA_FALLBACK_URL", raising=False)

    with _fake_ollama(_unit_vector(0)) as (url, requests):
        monkeypatch.setenv("LINSENKASTEN_OLLAMA_URL", url)
        match = lens_registry.resolve({"name": "fd-body-only", "focus": "queue"})

    assert match is not None
    assert match["id"] == "gen:fd-body-only@bbbbbbbb"
    assert match["method"] == "lexical"
    assert len(requests) == 1


def test_resolve_uses_lexical_when_embedding_model_does_not_match(
    tmp_path, monkeypatch, lens_registry
):
    root = tmp_path / "registry"
    _write_registry(root)
    (root / "data" / "embeddings" / "meta.json").write_text(
        json.dumps({"model": "other-768-model", "dim": EMBED_DIM}), encoding="utf-8"
    )
    monkeypatch.setenv("LINSENKASTEN_ROOT", str(root))
    monkeypatch.delenv("LINSENKASTEN_OLLAMA_FALLBACK_URL", raising=False)

    with _fake_ollama(_unit_vector(0)) as (url, requests):
        monkeypatch.setenv("LINSENKASTEN_OLLAMA_URL", url)
        match = lens_registry.resolve({"name": "fd-body-only", "focus": "queue"})

    assert match is not None
    assert match["id"] == "gen:fd-body-only@bbbbbbbb"
    assert match["method"] == "lexical"
    assert len(requests) == 1


def test_materialize_rerenders_registry_spec_and_overrides_reuse_frontmatter(
    tmp_path, monkeypatch, lens_registry
):
    root = tmp_path / "registry"
    _write_registry(root)
    monkeypatch.setenv("LINSENKASTEN_ROOT", str(root))
    monkeypatch.setenv("LINSENKASTEN_OLLAMA_URL", "http://127.0.0.1:1")
    monkeypatch.delenv("LINSENKASTEN_OLLAMA_FALLBACK_URL", raising=False)
    match = lens_registry.resolve({"name": "fd-canonical", "focus": "identity"})
    assert match is not None

    target = lens_registry.materialize(
        match,
        tmp_path / "agents",
        {"name": "fd-current-request", "source_spec_file": "current-spec.json"},
    )
    text = target.read_text(encoding="utf-8")
    frontmatter = _frontmatter(text)

    assert target.name == "fd-current-request.md"
    assert "Registry persona with clean source material." in text
    assert "A cutover strands active identities" in text
    assert "[truncated" not in text
    assert frontmatter["name"] == "fd-current-request"
    assert frontmatter["description"] == "identity migration boundary cutover"
    assert frontmatter["tier"] == "registry"
    assert frontmatter["registry_id"] == "gen:fd-canonical@aaaaaaaa"
    assert frontmatter["source_spec"] == "current-spec.json"
    assert frontmatter["cohort_siblings"] == ["fd-canonical", "fd-neighbor"]
    assert len(str(frontmatter["reused_at"])) == 10


def test_materialize_copies_only_clean_body_when_registry_has_no_spec(
    tmp_path, monkeypatch, lens_registry
):
    root = tmp_path / "registry"
    _write_registry(root)
    monkeypatch.setenv("LINSENKASTEN_ROOT", str(root))
    monkeypatch.setenv("LINSENKASTEN_OLLAMA_URL", "http://127.0.0.1:1")
    monkeypatch.delenv("LINSENKASTEN_OLLAMA_FALLBACK_URL", raising=False)
    match = lens_registry.resolve({"name": "fd-body-only", "focus": "queue"})
    assert match is not None

    target = lens_registry.materialize(
        match, tmp_path / "agents", {"name": "fd-queue-fairness"}
    )
    text = target.read_text(encoding="utf-8")
    frontmatter = _frontmatter(text)

    assert target.name == "fd-queue-fairness.md"
    assert "Keep this body verbatim." in text
    assert frontmatter["name"] == "fd-queue-fairness"
    assert frontmatter["description"] == "queue fairness backpressure"
    assert frontmatter["tier"] == "registry"
    assert text.endswith("# Body-only lens\n\nKeep this body verbatim.\n")


def test_materialize_rejects_invalid_registry_spec(tmp_path, monkeypatch, lens_registry):
    root = tmp_path / "registry"
    _write_registry(root)
    registry_spec = root / "data" / "generated" / "specs" / "gen:fd-canonical@aaaaaaaa.json"
    registry_spec.write_text(json.dumps({"name": 7, "focus": "identity"}), encoding="utf-8")
    monkeypatch.setenv("LINSENKASTEN_ROOT", str(root))
    monkeypatch.setenv("LINSENKASTEN_OLLAMA_URL", "http://127.0.0.1:1")
    monkeypatch.delenv("LINSENKASTEN_OLLAMA_FALLBACK_URL", raising=False)
    match = lens_registry.resolve({"name": "fd-canonical", "focus": "identity"})
    assert match is not None

    with pytest.raises(ValueError, match="invalid registry spec"):
        lens_registry.materialize(
            match,
            tmp_path / "agents",
            {"name": "fd-current-request", "source_spec_file": "current-spec.json"},
        )


def test_record_reuse_uses_registry_then_home_fallback(tmp_path, monkeypatch, lens_registry):
    root = tmp_path / "registry"
    _write_registry(root)
    entry = {
        "registry_id": "gen:fd-canonical@aaaaaaaa",
        "name": "fd-canonical",
        "score": 0.95,
        "method": "embedding",
        "embed_tier": "local",
        "consumer": "interflux",
        "project": "demo",
        "target": "plan.md",
        "ignored": "not persisted",
    }

    primary = lens_registry.record_reuse(root, entry)
    primary_row = json.loads(primary.read_text(encoding="utf-8").splitlines()[-1])
    assert primary == root / "data" / "generated" / "reuse-log.jsonl"
    assert primary_row["registry_id"] == entry["registry_id"]
    assert primary_row["recorded_at"].endswith("+00:00")
    assert "ignored" not in primary_row

    (root / "data" / "generated" / "reuse-log.jsonl").unlink()
    (root / "data" / "generated" / "reuse-log.jsonl").mkdir()
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    fallback = lens_registry.record_reuse(root, entry)

    assert fallback == tmp_path / "home" / ".local" / "share" / "linsenkasten" / "reuse-log.jsonl"
    assert json.loads(fallback.read_text(encoding="utf-8"))["name"] == "fd-canonical"
