#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

graphify update .

echo
echo "Graphify refreshed."
git status --short graphify-out .gitignore
