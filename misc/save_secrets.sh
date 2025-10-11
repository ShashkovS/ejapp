#!/usr/bin/env sh
# Сохраняет переменные из misc/secret_vars.txt в ./.codex/secrets.env.b64 (base64)
set -eu

# Абсолютный путь к папке скрипта (/misc)
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)"
# Корень репозитория — родитель misc
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd -P)"

LIST_FILE="${1:-${SCRIPT_DIR}/secret_vars.txt}"
OUT_DIR="${REPO_ROOT}/.codex"
OUT_FILE="${OUT_DIR}/secrets.env.b64"

umask 077
mkdir -p "${OUT_DIR}"

TMP_FILE="$(mktemp "${OUT_DIR}/secrets.env.b64.tmp.XXXXXX")"

while IFS= read -r NAME; do
  case "${NAME}" in
    ''|\#*) continue ;;
  esac
  if [ "${!NAME-__MISSING__}" = "__MISSING__" ]; then
    printf >&2 "warn: variable %s is not set; skipping\n" "${NAME}"
    continue
  fi
  VAL="${!NAME}"
  B64="$(printf %s "$VAL" | base64)"
  printf '%s=%s\n' "${NAME}" "${B64}" >> "${TMP_FILE}"
done < "${LIST_FILE}"

mv -f "${TMP_FILE}" "${OUT_FILE}"
chmod 600 "${OUT_FILE}"
printf 'saved: %s\n' "${OUT_FILE}"
