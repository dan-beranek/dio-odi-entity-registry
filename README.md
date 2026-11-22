# DIO/ODI Entity Registry

A public, versioned source of truth for the identity-level records shared across Daniel Beránek's public web and software projects.

The registry is deliberately separate from the sites that consume it. It stores stable entity identifiers and a small set of identity assertions; each consuming project remains responsible for generating its own context-appropriate Schema.org graph.

## Current state

- Registry version: `0.1.0`
- Registry status: `canonical-approved` — the seven initial shared identity records have been reconciled against the currently published project graphs. Adoption by each consuming build remains staged and version-pinned.
- Data file: [`entities.json`](./entities.json)
- JSON Schema: [`schemas/entity-registry.schema.json`](./schemas/entity-registry.schema.json)
- Validation: [`scripts/validate_registry.py`](./scripts/validate_registry.py)

## Scope and authority

This registry is authoritative for the shared identity fields it explicitly owns:

- stable `@id` values;
- declared entity types;
- preferred names;
- canonical entity URLs and, where relevant, service endpoints;
- verified `sameAs` identifiers;
- record status and provenance pointers.

It is **not** a universal Schema.org graph and does not centrally dictate page semantics. In particular:

- consuming sites own their page-level `WebPage`, `ProfilePage`, `WebSite`, `mainEntity`, `mainEntityOfPage`, `about` and `isPartOf` relationships;
- the Reference Model remains authoritative for canonical DIO/ODI SKOS concepts and definitions;
- the Reference Model's publication metadata registry remains authoritative for works, versions, DOIs and inter-publication relations;
- the keyword registry remains authoritative for keyword grammar and resolved keyword profiles;
- each project's generator remains responsible for descriptions and context-specific presentation.

The registry records the identity of the DIO/ODI Reference Vocabulary, but it does not duplicate or redefine its concepts.

## Data model

Each entity record contains a stable machine key, a canonical `@id`, one or more fully qualified type URIs, a preferred name, a canonical URL, an active/deprecated state, and source-record pointers. Optional fields include `sameAs`, a service endpoint, a landing page and a replacement URI for a deprecated record.

This is a registry format, not a standalone JSON-LD document. Consumers should resolve records and project the fields they need into their own graph rather than embedding the entire registry as page markup.

## Machine-readable distribution

The mutable discovery URL is:

```text
https://raw.githubusercontent.com/dan-beranek/dio-odi-entity-registry/main/entities.json
```

Use the `main` URL for discovery and development only. Production builds must pin an immutable Git commit SHA and record it in their build metadata. A release tag such as `v0.1.0` is a convenient human-readable alias, but the commit SHA remains the reproducibility anchor. Do not silently consume the moving `main` branch in production builds.

For a consumer, the preferred pattern is to vendor an exact snapshot from the pinned commit, verify that snapshot against the same immutable upstream commit in CI, and project only the required entity fields into the consumer's own graph. A snapshot is a build input, not a second authority.

## Validation

Run locally:

```bash
python -m pip install -r requirements.txt
python scripts/validate_registry.py
```

GitHub Actions runs the same validation on pushes and pull requests.

Validation checks the JSON Schema, unique record keys and entity identifiers, URI syntax, duplicate `sameAs` values, deprecation references, and the canonical Person identity invariant.

## Versioning and change control

The registry follows Semantic Versioning:

- **MAJOR** — breaking schema or identity migration that requires consumer changes;
- **MINOR** — additive entity records or backward-compatible fields;
- **PATCH** — corrections that do not change entity identity or the schema contract.

Entity `@id` values are persistent identifiers. Do not casually rename, recycle or repurpose them. If an entity is superseded, retain its old record as deprecated and provide `replaced_by`; do not silently delete or reassign its identifier.

A registry revision is eligible for production consumption only when the schema and identity invariants pass, the version is recorded, the change is reviewed, and the consuming project pins the immutable commit SHA. Git tags may be added as human-readable release aliases; they are not a substitute for immutable commit pins. Consumers should upgrade their pinned revision deliberately.

## Licensing

The repository is public, but no reuse licence is declared yet. Public visibility alone does not grant permission to reuse all repository contents. Add an explicit data licence before advertising the registry as openly licensed.

## Repository structure

```text
.
├── entities.json
├── schemas/
│   └── entity-registry.schema.json
├── scripts/
│   └── validate_registry.py
├── .github/
│   └── workflows/
│       └── validate.yml
├── requirements.txt
└── CHANGELOG.md
```
