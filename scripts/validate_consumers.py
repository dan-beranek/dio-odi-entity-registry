#!/usr/bin/env python3
"""Check that all registered projects consume the same immutable Entity Registry release."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
CONSUMERS_PATH = ROOT / "metadata" / "consumers.json"
USER_AGENT = "DIO-ODI-Entity-Registry-Consumer-Integrity/1.0"


def fetch(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urlopen(request, timeout=25) as response:
        return response.read()


def fail(message: str) -> None:
    raise SystemExit("CROSS-REPOSITORY INTEGRITY FAILED: " + message)


def main() -> int:
    registry = json.loads((ROOT / "entities.json").read_text(encoding="utf-8"))
    consumers = json.loads(CONSUMERS_PATH.read_text(encoding="utf-8"))

    if registry.get("status") != "canonical-approved":
        fail("the local Entity Registry is not canonical-approved")
    release = consumers.get("source_release", {})
    if release.get("registry_version") != registry.get("registry_version"):
        fail("consumer manifest release version differs from entities.json")
    commit = release.get("registry_commit", "")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        fail("source_release.registry_commit must be a full immutable commit SHA")

    canonical_url = (
        f"https://raw.githubusercontent.com/dan-beranek/dio-odi-entity-registry/"
        f"{commit}/{release.get('registry_path', 'entities.json')}"
    )
    try:
        canonical_bytes = fetch(canonical_url)
    except Exception as exc:
        fail(f"cannot retrieve pinned Entity Registry release: {exc}")

    local_bytes = (ROOT / "entities.json").read_bytes()
    if canonical_bytes != local_bytes:
        fail("entities.json has drifted from the approved immutable source release")

    canonical = json.loads(canonical_bytes)
    active_keys = {
        item.get("key")
        for item in canonical.get("entities", [])
        if item.get("status") == "active"
    }

    entries = consumers.get("consumers", [])
    if not entries:
        fail("consumer manifest must contain at least one registered consumer")
    seen_repositories: set[str] = set()
    failures: list[str] = []

    for item in entries:
        consumer_id = item.get("id", "<unnamed>")
        repository = item.get("repository", "")
        branch = item.get("branch", "main")
        lock_path = item.get("lock_path", "")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
            failures.append(f"{consumer_id}: invalid repository name")
            continue
        if repository in seen_repositories:
            failures.append(f"{consumer_id}: duplicate registered repository {repository}")
            continue
        seen_repositories.add(repository)
        if not lock_path or lock_path.startswith("/") or ".." in Path(lock_path).parts:
            failures.append(f"{consumer_id}: invalid lock_path")
            continue

        base = f"https://raw.githubusercontent.com/{repository}/{branch}"
        try:
            lock_bytes = fetch(f"{base}/{lock_path}")
            lock = json.loads(lock_bytes)
            if lock.get("registry_repository") != "dan-beranek/dio-odi-entity-registry":
                raise ValueError("lock points to an unexpected registry repository")
            if lock.get("registry_version") != release["registry_version"]:
                raise ValueError(
                    f"registry version {lock.get('registry_version')} != {release['registry_version']}"
                )
            if lock.get("registry_commit") != commit:
                raise ValueError(
                    f"pinned commit {lock.get('registry_commit')} != approved commit {commit}"
                )
            if lock.get("source_path") != release.get("registry_path", "entities.json"):
                raise ValueError("lock source_path differs from the approved release manifest")

            consumed = lock.get("consumed_entities", [])
            missing = set(consumed) - active_keys
            if missing:
                raise ValueError("consumed entity keys are missing or inactive: " + ", ".join(sorted(missing)))

            snapshot_path = lock.get("snapshot_path")
            if not snapshot_path or snapshot_path.startswith("/") or ".." in Path(snapshot_path).parts:
                raise ValueError("invalid snapshot_path in consumer lock")
            snapshot_bytes = fetch(f"{base}/{snapshot_path}")
            if snapshot_bytes != canonical_bytes:
                raise ValueError("vendored snapshot is not byte-identical to the approved release")
        except Exception as exc:
            failures.append(f"{consumer_id} ({repository}): {exc}")

    if failures:
        for failure in failures:
            print("ERROR: " + failure, file=sys.stderr)
        raise SystemExit(1)

    print(
        "Cross-repository Entity Registry integrity passed: "
        f"{len(entries)} consumers pin v{release['registry_version']} at {commit}; "
        "all snapshots are byte-identical."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
