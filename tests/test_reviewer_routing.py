import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "select-review-route.py"


def resolve(purpose: str, producer: str | None = None) -> dict:
    command = [sys.executable, str(SCRIPT), "--purpose", purpose]
    if producer:
        command += ["--producer", producer]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_bulk_mirror_stays_sol_high_fast():
    payload = resolve("bulk")
    assert payload["candidates"][0] == {
        "profile": "sol-bulk",
        "kind": "codex",
        "model": "gpt-5.6-sol",
        "reasoning_effort": "high",
        "service_tier": "fast",
        "invoke": payload["candidates"][0]["invoke"],
    }


def test_claude_producer_selects_astra_high_standard():
    candidate = resolve("validation", "claude/fable")["candidates"][0]
    assert candidate["model"] == "gpt-6-astra"
    assert candidate["reasoning_effort"] == "high"
    assert candidate["service_tier"] == "standard"
    assert candidate["minimum_codex_version"] == "0.153.1"
    assert 'service_tier="default"' in candidate["invoke"]


def test_kimi_producer_selects_astra():
    assert resolve("validation", "kimi/k3")["candidates"][0]["model"] == "gpt-6-astra"


def test_astra_producer_excludes_astra_and_prefers_external_fable():
    candidates = resolve("validation", "codex/gpt-6-astra")["candidates"]
    assert candidates[0]["kind"] == "claude"
    assert candidates[0]["model"] == "fable"
    assert all(item["model"] != "gpt-6-astra" for item in candidates)
    assert [item["model"] for item in candidates] == ["fable", "k3", "gpt-5.6-sol"]


def test_validation_requires_producer_identity():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--purpose", "validation"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "--producer" in result.stderr
