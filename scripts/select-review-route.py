#!/usr/bin/env python3
"""Resolve Interflux reviewer profiles without duplicating routing in a shell."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "flux-melange" / "defaults.yaml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--purpose", choices=("bulk", "validation"), required=True)
    parser.add_argument("--producer", help="producer identity as kind/model or kind:model")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    return parser.parse_args()


def parse_producer(value: str) -> tuple[str, str]:
    separator = "/" if "/" in value else ":"
    if separator not in value:
        raise ValueError("--producer must be kind/model or kind:model")
    kind, model = value.split(separator, 1)
    if not kind or not model:
        raise ValueError("--producer must include both kind and model")
    return kind, model


def resolve(config: dict, purpose: str, producer: str | None) -> dict:
    routing = config["reviewer_routing"]
    profiles = routing["profiles"]

    if purpose == "bulk":
        references = routing["routes"]["bulk"]
        producer_identity = None
    else:
        if not producer:
            raise ValueError("--producer is required for validation routing")
        producer_kind, producer_model = parse_producer(producer)
        validation = routing["routes"]["validation"]
        references = validation.get("producer_model", {}).get(producer_model)
        if references is None:
            references = validation.get("producer_kind", {}).get(
                producer_kind, validation["default"]
            )
        producer_identity = {"kind": producer_kind, "model": producer_model}

    candidates = []
    for reference in references:
        profile = dict(profiles[reference])
        if producer_identity and profile["model"] == producer_identity["model"]:
            continue
        candidates.append({"profile": reference, **profile})

    if not candidates:
        raise ValueError("routing produced no reviewer distinct from the producer model")

    return {
        "purpose": purpose,
        "producer_identity": producer_identity,
        "candidates": candidates,
    }


def main() -> int:
    args = parse_args()
    try:
        config = yaml.safe_load(args.config.read_text())
        payload = resolve(config, args.purpose, args.producer)
    except (KeyError, OSError, TypeError, ValueError, yaml.YAMLError) as exc:
        print(f"select-review-route: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
