#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

git add .gitignore graphify-out/GRAPH_REPORT.md graphify-out/GRAPH_TREE.html graphify-out/graph.html graphify-out/graph.json graphify-out/manifest.json graphify-out/2026-06-17/GRAPH_REPORT.md graphify-out/2026-06-17/graph.json graphify-out/2026-06-17/manifest.json scripts/refresh_graphify.sh scripts/stage_graphify.sh

echo "Graphify artifacts staged."
git status --short
