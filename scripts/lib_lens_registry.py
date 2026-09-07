"""Resolve and materialize generated review lenses from Linsenkasten.

This module deliberately has no dependency on ``scripts/lib_registry.py``;
that helper manages the unrelated model registry.
"""
from __future__ import annotations

import importlib.util
import json
import math
import os
import sys
import re
import struct
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any

import yaml


EMBED_MODEL = "nomic-embed-text"
EMBED_DIM = 768
RESOLVE_MIN_COSINE = 0.86
LEXICAL_MIN_JACCARD = 0.6
OLLAMA_TIMEOUT_SECONDS = 4.0

_INDEX_PATH = Path("data/generated/index.jsonl")
_NAME_PATTERN = re.compile(r"^fd-[a-z0-9]+(?:-[a-z0-9]+)*$")
_VECTOR_FORMAT = f"<{EMBED_DIM}f"
_GENERATE_AGENTS_MODULE: ModuleType | None = None
_REUSE_FIELDS = (
    "registry_id",
    "name",
    "score",
    "method",
    "embed_tier",
    "consumer",
    "project",
    "target",
)


# Copied verbatim from linsenkasten/harvest/thresholds.py on 2026-09-06.
def normalize_body(body: str) -> str:
    """The one normalization the content hash is taken over: frontmatter already stripped by the caller."""
    return re.sub(r"\s+", " ", body).strip()


def embedding_text(spec: dict | None, body: str) -> str:
    """The one recipe both layers use. Spec wins; body fallback is deterministic."""
    if spec:
        parts = [spec.get("persona", ""), spec.get("focus", ""), spec.get("decision_lens", "")]
        parts += list(spec.get("review_areas") or [])
        return "\n".join(p for p in parts if p).strip()
    import re
    m = re.search(r"^Apply the perspective.*?(?=\n\n)", body, re.S | re.M)
    heads = re.findall(r"^### \d+\. (.+)$", body, re.M)
    # Lead of the whitespace-normalized body (code points, not bytes): pre-v5 bodies have neither the persona
    # paragraph nor numbered headings, and an empty text embeds to one shared vector (2026-09-06 calibration:
    # a 28-member spurious cluster of empty-text records).
    lead = normalize_body(body)[:1200]
    return "\n".join(p for p in [m.group(0) if m else "", *heads, lead] if p).strip()


def _cache_version_key(path: Path) -> tuple[tuple[int, int | str], ...]:
    """Return a natural-sort key for plugin cache version directory names."""
    return tuple(
        (0, int(part)) if part.isdigit() else (1, part.lower())
        for part in re.findall(r"\d+|\D+", path.name)
    )


def _has_index(root: Path) -> bool:
    return (root / _INDEX_PATH).is_file()


def find_registry_root() -> Path | None:
    """Find the first usable Linsenkasten checkout or installed plugin."""
    candidates: list[Path] = []
    configured = os.environ.get("LINSENKASTEN_ROOT")
    if configured:
        candidates.append(Path(configured).expanduser())

    home = Path.home()
    candidates.extend(
        [
            home / "projects" / "Sylveste" / "interverse" / "linsenkasten",
            home / "projects" / "Sylveste" / "interverse" / "interlens",
        ]
    )

    cache_root = (
        home
        / ".claude"
        / "plugins"
        / "cache"
        / "interagency-marketplace"
        / "linsenkasten"
    )
    if cache_root.is_dir():
        cached = sorted(
            (path for path in cache_root.iterdir() if path.is_dir()),
            key=_cache_version_key,
            reverse=True,
        )
        candidates.extend(cached)

    seen: set[Path] = set()
    for candidate in candidates:
        candidate = candidate.expanduser()
        if candidate in seen:
            continue
        seen.add(candidate)
        if _has_index(candidate):
            return candidate
    return None


def load(root: str | os.PathLike[str] | None = None) -> list[dict[str, Any]]:
    """Load generated cluster heads from a registry, preserving index order."""
    registry_root = Path(root).expanduser() if root is not None else find_registry_root()
    if registry_root is None:
        return []

    heads: list[dict[str, Any]] = []
    index_path = registry_root / _INDEX_PATH
    with index_path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                # Reuse is best-effort: a torn or foreign line must not abort lens generation
                # (every other unavailability path in this module degrades instead of raising).
                print(f"lib_lens_registry: skipping invalid registry JSON at {index_path}:{line_number}", file=sys.stderr)
                continue
            if not isinstance(record, dict):
                print(f"lib_lens_registry: skipping non-object registry row at {index_path}:{line_number}", file=sys.stderr)
                continue
            cluster = record.get("cluster")
            if isinstance(cluster, dict) and cluster.get("head") is True:
                item = dict(record)
                item["_registry_root"] = str(registry_root)
                heads.append(item)
    return heads


def _record_path(
    root: Path,
    record: dict[str, Any],
    field: str,
    default: Path,
) -> Path:
    raw = record.get(field)
    relative = Path(str(raw)) if raw else default
    data_root = (root / "data").resolve()
    if relative.is_absolute():
        path = relative.resolve()
    elif relative.parts and relative.parts[0] == "data":
        path = (root / relative).resolve()
    else:
        path = (data_root / relative).resolve()
    if path != data_root and data_root not in path.parents:
        raise ValueError(f"registry {field} escapes data root: {relative}")
    return path


def _spec_path(root: Path, record: dict[str, Any]) -> Path | None:
    if "spec_path" in record and record["spec_path"] is None:
        return None
    return _record_path(
        root,
        record,
        "spec_path",
        Path("generated/specs") / f"{record['id']}.json",
    )


def _body_path(root: Path, record: dict[str, Any]) -> Path:
    return _record_path(
        root,
        record,
        "body_path",
        Path("generated/lenses") / f"{record['id']}.md",
    )


def _record_has_spec(root: Path, record: dict[str, Any]) -> bool:
    try:
        spec_path = _spec_path(root, record)
        return spec_path is not None and spec_path.is_file()
    except (KeyError, OSError, ValueError):
        return False


def _ollama_urls() -> list[tuple[str, str]]:
    urls = [(os.environ.get("LINSENKASTEN_OLLAMA_URL", "http://127.0.0.1:11434"), "local")]
    fallback = os.environ.get("LINSENKASTEN_OLLAMA_FALLBACK_URL")
    if fallback and fallback.rstrip("/") != urls[0][0].rstrip("/"):
        urls.append((fallback, "fallback"))
    return urls


def _embed(text: str) -> tuple[list[float], str] | None:
    payload = json.dumps({"model": EMBED_MODEL, "input": [text]}).encode("utf-8")
    for base_url, tier in _ollama_urls():
        request = urllib.request.Request(
            f"{base_url.rstrip('/')}/api/embed",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=OLLAMA_TIMEOUT_SECONDS) as response:
                result = json.load(response)
            embeddings = result.get("embeddings")
            if not isinstance(embeddings, list) or len(embeddings) != 1:
                raise ValueError("Ollama returned an unexpected embedding count")
            vector = embeddings[0]
            if (
                not isinstance(vector, list)
                or len(vector) != EMBED_DIM
                or any(not isinstance(value, (int, float)) or not math.isfinite(value) for value in vector)
            ):
                raise ValueError(f"Ollama returned an invalid {EMBED_DIM}-dimension embedding")
            return [float(value) for value in vector], tier
        except Exception:
            continue
    return None


def _load_generated_matrix(root: Path) -> tuple[list[str], bytes] | None:
    embeddings = root / "data" / "embeddings"
    try:
        ids = json.loads((embeddings / "generated.ids.json").read_text(encoding="utf-8"))
        data = (embeddings / "generated.f32").read_bytes()
        meta = json.loads((embeddings / "meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(ids, list) or not all(isinstance(item, str) for item in ids):
        return None
    if (
        not isinstance(meta, dict)
        or meta.get("model") != EMBED_MODEL
        or meta.get("dim") != EMBED_DIM
        or len(data) != len(ids) * EMBED_DIM * 4
    ):
        return None
    return ids, data


def _cosine(query: list[float], query_norm: float, data: bytes, row: int) -> float:
    vector = struct.unpack_from(_VECTOR_FORMAT, data, row * EMBED_DIM * 4)
    vector_norm = math.sqrt(sum(value * value for value in vector))
    if query_norm == 0 or vector_norm == 0:
        return 0.0
    return sum(left * right for left, right in zip(query, vector)) / (query_norm * vector_norm)


def _tokens(value: Any) -> set[str]:
    return {
        token
        for token in re.sub(r"[^a-z0-9\s]", " ", str(value or "").lower()).split()
        if len(token) > 2
    }


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _match(record: dict[str, Any], score: float, method: str, embed_tier: str) -> dict[str, Any]:
    result = dict(record)
    stats = record.get("stats") if isinstance(record.get("stats"), dict) else {}
    cohort = record.get("cohort") if isinstance(record.get("cohort"), dict) else {}
    result.update(
        {
            "registry_id": record["id"],
            "score": score,
            "method": method,
            "embed_tier": embed_tier,
            "hit_rate": stats.get("hit_rate"),
            "smoothed_hit_rate": stats.get("smoothed_hit_rate"),
            "adjudicated": stats.get("adjudicated", 0),
            "embodies": record.get("embodies") or [],
            "cohort_siblings": cohort.get("siblings") or record.get("cohort_siblings") or [],
        }
    )
    return result


def _lexical_resolve(spec: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    requested_name = str(spec.get("name") or "").strip().lower()
    if requested_name:
        exact = next(
            (record for record in candidates if str(record.get("name", "")).lower() == requested_name),
            None,
        )
        if exact is not None:
            return _match(exact, 1.0, "lexical", "lexical")

    focus = _tokens(spec.get("focus"))
    scored = [
        (_jaccard(focus, _tokens(record.get("summary"))), str(record.get("id", "")), record)
        for record in candidates
    ]
    scored.sort(key=lambda item: (-item[0], item[1]))
    if not scored or scored[0][0] < LEXICAL_MIN_JACCARD:
        return None
    score, _, record = scored[0]
    return _match(record, score, "lexical", "lexical")


def resolve(spec: dict[str, Any]) -> dict[str, Any] | None:
    """Resolve a flux-gen spec to the best reusable generated-lens head."""
    if not isinstance(spec, dict):
        raise TypeError("spec must be a dict")
    root = find_registry_root()
    if root is None:
        return None

    candidates = [
        record
        for record in load(root)
        if isinstance(record.get("id"), str)
        and record["id"].strip()
        and not (record.get("corrupt") and not _record_has_spec(root, record))
    ]
    if not candidates:
        return None

    text = embedding_text(spec, "")
    if not text:
        return _lexical_resolve(spec, candidates)

    embedded = _embed(text)
    if embedded is None:
        return _lexical_resolve(spec, candidates)

    loaded = _load_generated_matrix(root)
    if loaded is None:
        return _lexical_resolve(spec, candidates)
    ids, data = loaded
    candidates_by_id = {record.get("id"): record for record in candidates}
    query, tier = embedded
    query_norm = math.sqrt(sum(value * value for value in query))
    scores = [
        (_cosine(query, query_norm, data, row), lens_id, candidates_by_id[lens_id])
        for row, lens_id in enumerate(ids)
        if lens_id in candidates_by_id
    ]
    scores.sort(key=lambda item: (-item[0], item[1]))
    if not scores or scores[0][0] < RESOLVE_MIN_COSINE:
        return None
    score, _, record = scores[0]
    return _match(record, score, "embedding", tier)


def _load_generate_agents() -> ModuleType:
    global _GENERATE_AGENTS_MODULE
    if _GENERATE_AGENTS_MODULE is not None:
        return _GENERATE_AGENTS_MODULE

    module_path = Path(__file__).with_name("generate-agents.py")
    module_spec = importlib.util.spec_from_file_location("_interflux_generate_agents", module_path)
    if module_spec is None or module_spec.loader is None:
        raise RuntimeError(f"cannot import render_agent from {module_path}")
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    _GENERATE_AGENTS_MODULE = module
    return _GENERATE_AGENTS_MODULE


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end < 0:
        raise ValueError("agent file has unterminated YAML frontmatter")
    parsed = yaml.safe_load(text[4:end]) or {}
    if not isinstance(parsed, dict):
        raise ValueError("agent YAML frontmatter is not an object")
    return parsed, text[end + len("\n---\n") :]


def _render_with_frontmatter(text: str, overrides: dict[str, Any], drop: tuple[str, ...] = ()) -> str:
    frontmatter, body = _split_frontmatter(text)
    for key in drop:
        frontmatter.pop(key, None)
    frontmatter.update(overrides)
    rendered = yaml.safe_dump(
        frontmatter,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    ).rstrip()
    return f"---\n{rendered}\n---\n{body}"


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def materialize(
    match: dict[str, Any],
    agents_dir: str | os.PathLike[str],
    spec: dict[str, Any],
) -> Path:
    """Materialize a registry match under the current spec's filename."""
    name = spec.get("name") if isinstance(spec, dict) else None
    if not isinstance(name, str) or not _NAME_PATTERN.fullmatch(name):
        raise ValueError("spec name must be a safe fd-* identifier")

    root_value = match.get("_registry_root")
    root = Path(root_value) if root_value else find_registry_root()
    if root is None:
        raise FileNotFoundError("Linsenkasten registry is unavailable")

    registry_spec_path = _spec_path(root, match)
    registry_spec: dict[str, Any] | None = None
    current_spec_file = spec.get("source_spec_file") or spec.get("source_spec")
    generator = _load_generate_agents()
    if registry_spec_path is not None and registry_spec_path.is_file():
        raw_registry_spec = json.loads(registry_spec_path.read_text(encoding="utf-8"))
        spec_for_validation = (
            {**raw_registry_spec, "name": name}
            if isinstance(raw_registry_spec, dict)
            else raw_registry_spec
        )
        is_valid, validation_errors, registry_spec = generator.validate_agent_spec(
            spec_for_validation,
            name_pattern=_NAME_PATTERN.pattern,
        )
        if not is_valid:
            details = "; ".join(validation_errors)
            raise ValueError(f"invalid registry spec {registry_spec_path}: {details}")
        generated = generator.render_agent(
            {**registry_spec, "name": name},
            source_spec_file=str(current_spec_file) if current_spec_file else None,
        )
    else:
        if match.get("corrupt"):
            raise ValueError("refusing to copy a corrupt registry body without a spec")
        generated = _body_path(root, match).read_text(encoding="utf-8")

    description_candidates = (
        [registry_spec.get("focus")] if registry_spec else [match.get("summary")]
    )
    description_candidates.extend(
        [spec.get("description"), spec.get("focus"), f"Registry lens {name}"]
    )
    description = next(
        (
            cleaned
            for candidate in description_candidates
            if (cleaned := generator.sanitize(candidate))
        ),
        generator.sanitize(f"Registry lens {name}"),
    )

    overrides: dict[str, Any] = {
        "name": name,
        "description": str(description).strip(),
        "generated_by": "flux-gen-prompt",
        "tier": "registry",
        "registry_id": match.get("registry_id") or match["id"],
        "reused_at": datetime.now(timezone.utc).date().isoformat(),
        "cohort_siblings": _cohort_siblings(match),
    }
    if current_spec_file:
        overrides["source_spec"] = str(current_spec_file)

    # A copied body carries the registry record's own provenance; none of it describes this reuse.
    stale = ("source_spec", "use_count", "last_used", "generated_at", "registry_id", "reused_at")
    target = Path(agents_dir) / f"{name}.md"
    _atomic_write(target, _render_with_frontmatter(generated, overrides, drop=stale))
    return target


def _cohort_siblings(match: dict[str, Any]) -> list[str]:
    explicit = match.get("cohort_siblings")
    if isinstance(explicit, list):
        return [str(item) for item in explicit]
    cohort = match.get("cohort")
    if isinstance(cohort, dict):
        siblings = cohort.get("siblings")
        return [str(item) for item in siblings] if isinstance(siblings, list) else []
    if isinstance(cohort, list):
        return [str(item) for item in cohort]
    return []


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True, default=str) + "\n")


def record_reuse(
    root: str | os.PathLike[str] | None,
    entry: dict[str, Any],
) -> Path:
    """Append a reuse event to the registry, falling back outside prune roots."""
    row = {field: entry.get(field) for field in _REUSE_FIELDS}
    row["recorded_at"] = datetime.now(timezone.utc).isoformat()

    if root is not None:
        primary = Path(root).expanduser() / "data" / "generated" / "reuse-log.jsonl"
        try:
            _append_jsonl(primary, row)
            return primary
        except (OSError, TypeError, ValueError):
            pass

    fallback = Path.home() / ".local" / "share" / "linsenkasten" / "reuse-log.jsonl"
    _append_jsonl(fallback, row)
    return fallback
