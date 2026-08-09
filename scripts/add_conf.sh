#!/usr/bin/env bash
# Convert raw DBLP bib files into rebiber json and register them in bib_list.txt.
#
# Run from anywhere (intended from the repo root):
#   bash scripts/add_conf.sh iclr 2025 2026
#
# Expects rebiber/raw_data/{conf}{year}.bib (or partials {conf}{year}_*.bib).

set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: bash scripts/add_conf.sh <conf> <year> [year...]" >&2
  echo "Example: bash scripts/add_conf.sh iclr 2025 2026" >&2
  exit 1
fi

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)
RAW_DATA="$REPO_ROOT/rebiber/raw_data"
DATA="$REPO_ROOT/rebiber/data"
BIB_LIST="$REPO_ROOT/rebiber/bib_list.txt"

conf_name=$1
shift

mkdir -p "$RAW_DATA" "$DATA"

run_bib2json() {
  local input=$1
  local output=$2
  if PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}" python -m rebiber.bib2json -i "$input" -o "$output"; then
    return 0
  fi
  echo "python -m rebiber.bib2json failed; falling back to rebiber/bib2json.py" >&2
  python "$REPO_ROOT/rebiber/bib2json.py" -i "$input" -o "$output"
}

for year in "$@"; do
  bibfile="$RAW_DATA/${conf_name}${year}.bib"
  jsonfile="$DATA/${conf_name}${year}.bib.json"
  entry="data/${conf_name}${year}.bib.json"

  if [[ ! -f "$bibfile" ]]; then
    echo "$bibfile does not exist, trying to concatenate partial files:"
    echo "$RAW_DATA/${conf_name}${year}_*.bib"
    shopt -s nullglob
    parts=("$RAW_DATA/${conf_name}${year}_"*.bib)
    shopt -u nullglob
    if [[ ${#parts[@]} -eq 0 ]]; then
      echo "No bib or partial files found for ${conf_name} ${year}" >&2
      exit 1
    fi
    cat "${parts[@]}" > "$bibfile"
  fi

  echo "${conf_name}-${year}"
  run_bib2json "$bibfile" "$jsonfile"

  if [[ -f "$BIB_LIST" ]] && grep -qxF "$entry" "$BIB_LIST"; then
    echo "$entry already listed in $BIB_LIST"
  else
    echo "$entry" >> "$BIB_LIST"
    echo "Appended $entry to $BIB_LIST"
  fi
done
