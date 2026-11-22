#!/usr/bin/env python3
"""Validate the DIO/ODI Entity Registry and its shared identity invariants."""
from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "entities.json"
SCHEMA_PATH = ROOT / "schemas" / "entity-registry.schema.json"
VERSION_PATTERN = re.compile(r"^\\d+\\.\\d+\\.\\d+$")

EXPECTED_ENTITIES = {
    "person-daniel-beranek": {
        "@id": "https://danielberanek.cz/#person",
        "@type": ["https://schema.org/Person"],
        "name": "Daniel Beránek",
        "url": "https://danielberanek.cz/od-pultu-az-k-seo-a-copy-s-ostrymi-hroty-profesni-bio/",
    },
    "project-dio-odi-reference-model": {
        "@id": "https://vocab.danielberanek.cz/#reference-model",
        "@type": ["https://schema.org/CreativeWork"],
        "name": "DIO/ODI Reference Model",
        "url": "https://vocab.danielberanek.cz/",
    },
    "vocabulary-dio-odi-reference": {
        "@id": "https://vocab.danielberanek.cz/dio-odi/#ReferenceVocabulary",
        "@type": ["https://schema.org/DefinedTermSet"],
        "name": "DIO/ODI Reference Vocabulary",
        "url": "https://vocab.danielberanek.cz/dio-odi/",
    },
    "software-agentic-er-guardrail-planner": {
        "@id": "https://apps.danielberanek.cz/agentic-entity-resolution-guardrail-planner/#software",
        "@type": ["https://schema.org/SoftwareApplication"],
        "name": "Agentic Entity Resolution Guardrail Planner",
        "url": "https://apps.danielberanek.cz/agentic-entity-resolution-guardrail-planner/",
    },
    "service-dio-odi-mcp-api": {
        "@id": "https://mcp.danielberanek.cz/#webapi",
        "@type": ["https://schema.org/WebAPI"],
        "name": "DIO/ODI MCP",
        "url": "https://mcp.danielberanek.cz/mcp",
        "landing_page": "https://mcp.danielberanek.cz/",
    },
    "software-dio-odi-mcp": {
        "@id": "https://mcp.danielberanek.cz/#software",
        "@type": ["https://schema.org/SoftwareApplication"],
        "name": "DIO/ODI MCP",
        "url": "https://mcp.danielberanek.cz/",
    },
    "framework-dio-odi-author-led": {
        "@id": "https://dan-beranek.github.io/dio-odi-autorsky-koncept/#framework",
        "@type": ["https://schema.org/CreativeWork"],
        "name": "DIO/ODI author-led framework",
        "url": "https://dan-beranek.github.io/dio-odi-autorsky-koncept/",
    },
}

EXPECTED_ORCID = "https://orcid.org/0009-0004-0050-0264"


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def is_https_uri(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def main() -> None:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(registry), key=lambda error: list(map(str, error.path)))
    if errors:
        for error in errors:
            location = ".".join(map(str, error.path)) or "<root>"
            print(f"Schema error at {location}: {error.message}", file=sys.stderr)
        raise SystemExit(1)

    if not VERSION_PATTERN.fullmatch(registry["registry_version"]):
        fail("registry_version must use MAJOR.MINOR.PATCH.")
    if registry["schema_version"] != "1.0.0":
        fail("Unexpected registry schema_version; update the validator deliberately.")
    if registry["status"] != "canonical-approved":
        fail("The initial production registry must be explicitly canonical-approved.")

    created = date.fromisoformat(registry["created"])
    updated = date.fromisoformat(registry["updated"])
    if updated < created:
        fail("Registry updated date cannot precede its creation date.")

    entities = registry["entities"]
    keys: set[str] = set()
    entity_ids: set[str] = set()
    same_as_index: dict[str, str] = {}
    by_key: dict[str, dict] = {}

    for entity in entities:
        key = entity["key"]
        entity_id = entity["@id"]
        if key in keys:
            fail(f"Duplicate entity key: {key}")
        if entity_id in entity_ids:
            fail(f"Duplicate entity @id: {entity_id}")
        keys.add(key)
        entity_ids.add(entity_id)
        by_key[key] = entity

        for field in ("@id", "url", "endpoint_url", "landing_page", "replaced_by"):
            value = entity.get(field)
            if value is not None and not is_https_uri(value):
                fail(f"{key}: {field} must be an absolute HTTPS URI.")

        for type_uri in entity["@type"]:
            if not is_https_uri(type_uri):
                fail(f"{key}: every @type must be an absolute HTTPS URI.")

        for same_as in entity.get("sameAs", []):
            if not is_https_uri(same_as):
                fail(f"{key}: sameAs values must be absolute HTTPS URIs.")
            if same_as == entity_id:
                fail(f"{key}: sameAs must not repeat its own @id.")
            previous = same_as_index.get(same_as)
            if previous:
                fail(f"sameAs URI {same_as} is assigned to both {previous} and {key}.")
            same_as_index[same_as] = key

        if entity["status"] == "deprecated" and entity.get("replaced_by") == entity_id:
            fail(f"{key}: a deprecated entity cannot replace itself.")

    missing = set(EXPECTED_ENTITIES) - set(by_key)
    if missing:
        fail("Missing required shared identities: " + ", ".join(sorted(missing)))

    for key, expected in EXPECTED_ENTITIES.items():
        entity = by_key[key]
        for field, expected_value in expected.items():
            if entity.get(field) != expected_value:
                fail(f"{key}: {field} diverges from the approved identity invariant.")
        if entity["status"] != "active":
            fail(f"{key}: required shared identity must remain active.")

    person = by_key["person-daniel-beranek"]
    if person.get("sameAs") != [EXPECTED_ORCID]:
        fail("The canonical Person sameAs must contain only the verified ORCID identifier.")

    for entity in entities:
        replacement = entity.get("replaced_by")
        if replacement and replacement not in entity_ids:
            if replacement.startswith("https://github.com/dan-beranek/dio-odi-entity-registry/"):
                fail(f"{entity['key']}: local replaced_by target does not resolve: {replacement}")

    print(
        "DIO/ODI Entity Registry is valid: "
        f"{len(entities)} entities, {len(keys)} unique keys, "
        f"{len(entity_ids)} unique @id values, registry v{registry['registry_version']} "
        f"({registry['status']})."
    )


if __name__ == "__main__":
    main()
