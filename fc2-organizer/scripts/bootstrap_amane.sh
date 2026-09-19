#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UPSTREAM="$ROOT/upstream"
AMANE="$UPSTREAM/amane"

mkdir -p "$UPSTREAM"

if [ -d "$AMANE" ]; then
  echo "upstream/amane already exists. No changes made."
  exit 0
fi

git clone https://github.com/sqzw-x/amane.git "$AMANE"
cd "$AMANE"
git checkout v0.15.0
git rev-parse HEAD

echo "Amane v0.15.0 cloned as read-only reference target."
