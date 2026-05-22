# MHM Provenance

Reusable provenance primitives for Mental Health Mission data processing.

This repository contains generic hashing, manifest, operation, binding,
source-state, and verification primitives. CONNECT-specific slice, issue, and
study workflows live in CONNECT repositories.

## Install

```sh
python -m venv .venv
. .venv/bin/activate
pip install -e .
python scripts/check_provenance_package_contract.py
```

This branch was extracted from
`connect-summary@011391223d0acaa28eb4c19ad5cd3e8f3e022d0b`.
