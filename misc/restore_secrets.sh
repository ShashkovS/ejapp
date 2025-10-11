#!/usr/bin/env sh
# Восстанавливает переменные окружения из ./.codex/secrets.env.b64
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd -P)"

IN_FILE="${1:-${REPO_ROOT}/.codex/secrets.env.b64}"

if [ ! -f "$IN_FILE" ]; then
  printf >&2 'error: secrets file not found: %s\n' "$IN_FILE"
  exit 1
fi

# Читаем строки вида NAME=BASE64 и экспортируем
while IFS= read -r LINE || [ -n "$LINE" ]; do
  [ -z "$LINE" ] && continue
  case "$LINE" in \#*) continue ;; esac

  NAME="${LINE%%=*}"
  B64="${LINE#*=}"

  # GNU: -d, BSD/macOS: -D
  VAL="$(printf %s "$B64" | base64 -d 2>/dev/null || printf %s "$B64" | base64 -D)"
  # Экспортируем как переменную окружения текущего процесса
  # shellcheck disable=SC2163
  export "$NAME=$VAL"
done <"$IN_FILE"

printf 'restored %s\n' "$IN_FILE"
