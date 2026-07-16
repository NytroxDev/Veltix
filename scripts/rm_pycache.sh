#!/usr/bin/env bash

set -e

echo "Removing __pycache__ directories..."

find . -type d -name "__pycache__" -prune -exec rm -rf {} +

echo "Done."