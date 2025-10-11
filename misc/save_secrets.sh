#!/usr/bin/env sh
# Сохраняет указанные в secret_vars.txt переменные окружения в .codex/secrets.env.b64
# Формат: NAME=BASE64_VALUE (по одной паре на строку)

set -eu

LIST_FILE="${1:-secret_vars.txt}"
OUT_DIR=".codex"
OUT_FILE="${OUT_DIR}/secrets.env.b64"

# Жёсткие права на каталог/файл
umask 077
mkdir -p "${OUT_DIR}"

# Пишем атомарно во временный файл, затем mv
TMP_FILE="$(mktemp "${OUT_DIR}/secrets.env.b64.tmp.XXXXXX")"

# Обойдём список переменных и сохраним их значения в base64
while IFS= read -r NAME; do
  # пропускаем пустые строки и комментарии
  case "${NAME}" in
    ''|\#*) continue ;;
  esac

  # Проверка наличия переменной
  if [ "${!NAME-__MISSING__}" = "__MISSING__" ]; then
    printf >&2 "warn: variable %s is not set; skipping\n" "${NAME}"
    continue
  fi

  # Бережно кодируем в base64 (без добавления лишних символов)
  VAL="${!NAME}"
  # shellcheck disable=SC2005
  B64="$(printf %s "$VAL" | base64)"

  printf '%s=%s\n' "${NAME}" "${B64}" >> "${TMP_FILE}"
done < "${LIST_FILE}"

# Атомарная замена
mv -f "${TMP_FILE}" "${OUT_FILE}"

# Дублируем права
chmod 600 "${OUT_FILE}"

printf 'saved: %s\n' "${OUT_FILE}"
