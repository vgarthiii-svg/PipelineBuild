#!/bin/bash
# Run the full test suite. Isolated from data/pipeline.db by fixtures.
cd "$(dirname "$0")/.." || exit 1
PYTHONPATH=/Users/vinnieg/Library/Python/3.9/lib/python/site-packages python3 -m pytest "$@"
