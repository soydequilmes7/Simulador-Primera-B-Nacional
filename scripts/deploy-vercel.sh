#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PROJECT_NAME="simulador-primera-b-nacional"
PRODUCTION_DOMAIN="https://simuladorprimerab.xyz"

TARGET="--prod"
if [[ "${1:-}" == "--preview" ]]; then
  TARGET=""
elif [[ "${1:-}" != "" && "${1:-}" != "--prod" ]]; then
  echo "Uso: $0 [--prod|--preview]" >&2
  exit 2
fi

if ! command -v vercel >/dev/null 2>&1; then
  echo "Error: no encuentro la CLI de Vercel. Instalá con: npm i -g vercel" >&2
  exit 1
fi

if [[ ! -f ".vercel/project.json" ]]; then
  echo "Error: falta .vercel/project.json. Corré 'vercel link' antes de deployar." >&2
  exit 1
fi

if ! grep -q "\"projectName\": \"$PROJECT_NAME\"" .vercel/project.json; then
  echo "Error: este repo no parece linkeado al proyecto Vercel esperado: $PROJECT_NAME" >&2
  exit 1
fi

echo "Sincronizando main con origin/main..."
git pull --ff-only origin main

if [[ -n "$(git status --porcelain)" ]]; then
  echo "Aviso: hay cambios locales sin commitear. Vercel deploya el estado local actual."
  git status --short
  echo
fi

echo "Deployando a Vercel..."
vercel deploy ${TARGET} --yes

if [[ -n "$TARGET" ]]; then
  echo
  echo "Verificando dominio de producción..."
  curl -fsSI "$PRODUCTION_DOMAIN/index.html" >/dev/null
  echo "OK: $PRODUCTION_DOMAIN/index.html responde."
fi
