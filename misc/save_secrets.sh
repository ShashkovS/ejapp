#!/usr/bin/env sh
# Сохраняет переменные из misc/secret_vars.txt в ./.codex/secrets.env.b64 (base64)
# Работает в /bin/sh (dash). Не использует ${!VAR}.
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd -P)"

LIST_FILE="${1:-${SCRIPT_DIR}/secret_vars.txt}"
OUT_DIR="${REPO_ROOT}/.codex"
OUT_FILE="${OUT_DIR}/secrets.env.b64"

umask 077
mkdir -p "${OUT_DIR}"

TMP_FILE="$(mktemp "${OUT_DIR}/secrets.env.b64.tmp.XXXXXX")"

# Читаем список имён и сохраняем только существующие (export'ed) переменные
while IFS= read -r NAME || [ -n "$NAME" ]; do
  case "$NAME" in
    ''|\#*) continue ;;
  esac

  # Пытаемся получить значение из окружения (printenv возвращает 0, даже если пусто)
  # Если переменной нет вовсе — код возврата не 0 (GNU/BusyBox). На BSD тоже ок.
  if VAL="$(printenv "$NAME" 2>/dev/null)"; then
    # Кодируем в base64 без лишних символов
    B64="$(printf %s "$VAL" | base64)"
    printf '%s=%s\n' "$NAME" "$B64" >>"$TMP_FILE"
  else
    printf >&2 'warn: variable %s is not set; skipping\n' "$NAME"
  fi
done <"$LIST_FILE"

mv -f "$TMP_FILE" "$OUT_FILE"
chmod 600 "$OUT_FILE"
printf 'saved: %s\n' "$OUT_FILE"
