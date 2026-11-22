#!/usr/bin/env python3
"""Validate the DIO/ODI Entity Registry and its identity invariants."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "entities.json"
SCHEMA_PATH = ROOT / "schemas" / "entity-registry.schema.json"

EXPECTED_PERSON_ID = "https://danielberanek.cz/#person"
EXPECTED_PERSON_URL = "https://danielberanek.cz/od-pultu-az-k-seo-a-copy-s-ostrymi-hroty-profesni-bio/"
EXPECTED_ORCID = "https://orcid.org/0009-0004-0050-0264"
VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")


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

    entities = registry["entities"]
    keys: set[str] = set()
    entity_ids: set[str] = set()
    same_as_index: dict[str, str] = {}
    by_id: dict[str, dict] = {}

    for entity in entities:
        key = entity["key"]
        entity_id = entity["@id"]
        if key in keys:
            fail(f"Duplicate entity key: {key}")
        if entity_id in entity_ids:
            fail(f"Duplicate entity @id: {entity_id}")
        keys.add(key)
        entity_ids.add(entity_id)
        by_id[entity_id] = entity

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

    person_matches = [entity for entity in entities if entity["@id"] == EXPECTED_PERSON_ID]
    if len(person_matches) != 1:
        fail("The registry must contain exactly one canonical Daniel Beránek Person record.")

    person = person_matches[0]
    if "https://schema.org/Person" not in person["@type"]:
        fail("The canonical Daniel Beránek entity must retain schema:Person type.")
    if person["url"] != EXPECTED_PERSON_URL:
        fail("Person.url must remain the canonical professional biography URL.")
    if person.get("sameAs") != [EXPECTED_ORCID]:
        fail("The canonical Person sameAs must contain the verified ORCID identifier.")

    for entity in entities:
        replacement = entity.get("replaced_by")
        if replacement and replacement not in entity_ids:
            # External replacement URIs are allowed, but local replacements should resolve.
            if replacement.startswith("https://github.com/dan-beranek/dio-odi-entity-registry/"):
                fail(f"{entity['key']}: local replaced_by target does not resolve: {replacement}")

    print(
        "DIO/ODI Entity Registry is valid: "
        f"{len(entities)} entities, {len(keys)} unique keys, "
        f"{len(entity_ids)} unique @id values, registry v{registry['registry_version']}."
    )


if __name__ == "__main__":
    main()
