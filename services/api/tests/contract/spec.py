"""Validate HTTP responses against contracts/openapi.yaml. BOSS-owned."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

SPEC_PATH = Path(__file__).resolve().parents[4] / "contracts" / "openapi.yaml"


@lru_cache(maxsize=1)
def spec() -> dict[str, Any]:
    return yaml.safe_load(SPEC_PATH.read_text())


def operations() -> list[tuple[str, str, str]]:
    """(method, path, operationId) for every operation."""
    out = []
    for path, item in spec()["paths"].items():
        for method, op in item.items():
            out.append((method.upper(), path, op["operationId"]))
    return out


def _resolve(node: dict[str, Any]) -> dict[str, Any]:
    while "$ref" in node:
        parts = node["$ref"].removeprefix("#/").split("/")
        cur: Any = spec()
        for p in parts:
            cur = cur[p]
        node = cur
    return node


def validate(method: str, path: str, status: int, body: Any) -> None:
    """Raise AssertionError if the status is undeclared or the body does not match."""
    op = spec()["paths"][path][method.lower()]
    responses = op["responses"]
    assert str(status) in responses, f"{method} {path}: status {status} not declared ({list(responses)})"
    resp = _resolve(responses[str(status)])
    content = resp.get("content", {}).get("application/json")
    if content is None:
        return
    schema = content["schema"]
    registry = Registry().with_resource("urn:spec", Resource.from_contents(spec(), default_specification=DRAFT202012))
    wrapped = {"$ref": "urn:spec#" + schema["$ref"].removeprefix("#")}
    errors = sorted(Draft202012Validator(wrapped, registry=registry).iter_errors(body), key=str)
    assert not errors, f"{method} {path} {status}: " + "; ".join(e.message for e in errors[:5])
