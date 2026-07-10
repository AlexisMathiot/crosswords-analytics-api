#!/usr/bin/env bash
# Déploiement PROD analytics — à lancer sur le VPS depuis n'importe où : ./deploy/deploy-prod.sh
# Séquence : pull main → rebuild image → restart conteneur.
set -euo pipefail
cd "$(dirname "$0")/.."

COMPOSE="docker compose -f compose.prod.yaml"

branch=$(git rev-parse --abbrev-ref HEAD)
if [ "$branch" != "main" ]; then
    echo "⛔ La stack prod déploie 'main', mais le checkout est sur '$branch'." >&2
    exit 1
fi

git pull --ff-only
$COMPOSE up -d --build

echo "✅ Analytics déployée — $(git log -1 --oneline)"
