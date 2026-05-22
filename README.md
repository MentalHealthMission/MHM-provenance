# MHM Provenance

Python tools for recording and verifying file-backed research provenance.

Use this package to describe source states, processing operations, selected
data slices, generated artefacts, and verification records.

## What You Can Do

- hash files, directories, and structured records
- write source-state and dataset manifests
- record operations, bindings, and generated artefacts
- attach governance, knowledge, and context references
- resolve materialized artefact paths
- verify manifest bundles after creation

## Install

```sh
python -m venv .venv
. .venv/bin/activate
pip install -e .
python scripts/check_provenance_package_contract.py
```
