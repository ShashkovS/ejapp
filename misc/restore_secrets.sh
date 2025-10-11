#!/usr/bin/env sh
# Восстанавливает переменные окружения из .codex/secrets.env.b64 и экспортирует их

set -eu

IN_FILE="${1:-.codex/secrets.env.b64}"

if [ ! -f "${IN_FILE}" ]; then
  printf >&2 'error: secrets file not found: %s\n' "${IN_FILE}"
  exit 1
fi

# Читаем файл построчно: NAME=BASE64
while IFS= read -r LINE; do
  [ -z "${LINE}" ] && continue
  # пропускаем комментарии
  case "${LINE}" in
    \#*) continue ;;
  esac

  NAME="${LINE%%=*}"
  B64="${LINE#*=}"

  # Декодируем значение; поддержка GNU/BSD base64
  # shellcheck disable=SC2155
  VAL="$(printf %s "${B64}" | base64 -d 2>/dev/null || printf %s "${B64}" | base64 -D)"

  # Экспорт в окружение текущего процесса
  # Используем printf %s | xargs для безопасной передачи без интерпретации
  # но здесь проще напрямую:
  export "${NAME}=${VAL}"
done < "${IN_FILE}"

# Для отладки можно раскомментировать:
# env | grep -E '^(EJUDGE_TOKEN|GOOGLE_CLIENT_ID|SECRET_KEY|GOOGLE_CLIENT_SECRET)=' >/dev/null

printf 'restored %s\n' "${IN_FILE}"
