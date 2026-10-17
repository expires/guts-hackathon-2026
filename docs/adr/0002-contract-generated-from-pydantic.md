# ADR 0002: Generate openapi.yaml from shared Pydantic models

- Status: accepted
- Date: 2026-10-17

## Context
The spec requires an API-first contract with examples, and backend validation against the same file. Eight workers build in parallel. Hand-written YAML drifts from code.

## Decision
- `services/api/lifeline_contracts/` holds every wire model (BOSS-owned).
- `contracts/build_openapi.py` builds `contracts/openapi.yaml` from those models plus hand-written paths.
- Examples are model instances, so each example is valid against its schema.
- Optional fields are omitted from responses (`exclude_none`). The build strips `null` from `anyOf` so `swift-openapi-generator` emits plain Swift optionals.
- The contract test suite validates live responses against `contracts/openapi.yaml`.

## Consequences
- One change point for wire shapes. A model change needs `make contract` and a Swift client regeneration.
- The YAML file carries a "generated, do not hand-edit" header.
