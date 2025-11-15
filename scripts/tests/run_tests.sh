#!/bin/bash
# Navigate to repository root (two levels up from scripts/tests/)
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

export PYTHONPATH=src:$PYTHONPATH
.venv/bin/python -m pytest tests/supervision/ -v --tb=line "$@"
