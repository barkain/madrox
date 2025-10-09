#!/bin/bash
export PYTHONPATH=src:$PYTHONPATH
.venv/bin/python -m pytest tests/supervision/ -v --tb=line "$@"
