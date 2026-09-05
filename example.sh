#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  printf '%s\n' 'Usage: bash example.sh REQUEST_JSON OUTPUT_SAVE' >&2
  exit 1
fi
input=$1
output=$2
if [[ -e "$output" || -L "$output" ]]; then
  printf '%s\n' 'Output already exists' >&2
  exit 1
fi
base=${BCSFE_API_URL:-https://battle-cats-save-file-editor-api.vercel.app}
while [[ "$base" == */ ]]; do base=${base%/}; done
if [[ ! "$base" =~ ^https?://[^/?#@]+(/[^?#]*)?$ ]]; then
  printf '%s\n' 'BCSFE_API_URL must be an HTTP(S) base URL without credentials, query, or fragment' >&2
  exit 1
fi
if [[ ! -f "$input" ]] || (( $(wc -c < "$input") > 2097152 )); then
  printf '%s\n' 'Request must be a file of at most 2 MiB' >&2
  exit 1
fi
temporary=$(mktemp)
created=false
cleanup() {
  status=$?
  rm -f -- "$temporary"
  if [[ "$created" == true && "$status" -ne 0 ]]; then rm -f -- "$output"; fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
if ! metadata=$(curl --disable --silent --show-error \
  --connect-timeout 15 --max-time 120 --max-filesize 2097152 \
  --request POST "${base}/v2/save/edit" \
  --header 'Content-Type: application/json' \
  --header 'Accept: application/octet-stream' \
  --data-binary "@${input}" --output "$temporary" \
  --write-out $'%{http_code}\n%{content_type}'); then
  printf '%s\n' 'HTTP request failed' >&2
  exit 1
fi
status=${metadata%%$'\n'*}
status=${status//[[:space:]]/}
content_type=${metadata#*$'\n'}
content_type=${content_type%%;*}
content_type=${content_type//[[:space:]]/}
if [[ ! "$status" =~ ^2[0-9][0-9]$ || "${content_type,,}" != application/octet-stream ]]; then
  printf 'Expected a binary success response; HTTP %s\n' "$status" >&2
  exit 1
fi
if (( $(wc -c < "$temporary") > 2097152 )); then
  printf '%s\n' 'Response exceeds 2 MiB' >&2
  exit 1
fi
set -o noclobber
exec 3> "$output"
created=true
set +o noclobber
cat -- "$temporary" >&3
exec 3>&-
printf 'Saved %s bytes to %s\n' "$(wc -c < "$temporary")" "$output"
