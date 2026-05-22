# MHM Provenance

Reusable provenance primitives for Mental Health Mission data processing and
other file-backed research workflows.

This repository contains generic hashing, manifest, operation, binding,
source-state, and verification primitives. It is deliberately lightweight: the
package records what was observed, which slice or operation was applied, which
artefacts were produced, and how those records can be verified later.

## What This Package Owns

- file and structured-data hashing
- source-state and manifest models
- operation and binding records
- governance, knowledge, and context references
- realization/path helpers for materialized artefacts
- verification helpers for manifest bundles

## Install

```sh
python -m venv .venv
. .venv/bin/activate
pip install -e .
python scripts/check_provenance_package_contract.py
```
