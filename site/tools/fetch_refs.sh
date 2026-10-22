#!/usr/bin/env bash
# Reference fonts for the study pages (punct, symbols, accents, coverage), under SIL OFL 1.1.
# Browser runtime/comparison fonts and their licenses are pinned in comparison_refs.tsv.
set -euo pipefail
manifest="$(cd "$(dirname "$0")" && pwd)/comparison_refs.tsv"
cd "$(dirname "$0")/../refs" 2>/dev/null || { mkdir -p "$(dirname "$0")/../refs"; cd "$(dirname "$0")/../refs"; }
B=https://raw.githubusercontent.com/google/fonts/main/ofl
# Cache only completed transfers; a failed partial file must never satisfy the next run.
get() {
    local expected=${3:-}
    if [ -s "$1" ]; then
        if [ -z "$expected" ] || verify "$1" "$expected"; then
            return 0
        fi
    fi
    local temp status
    temp=$(mktemp "$1.part.XXXXXX")
    if curl -fsSL --connect-timeout 5 --max-time 60 -o "$temp" "$2"; then
        if [ ! -s "$temp" ]; then
            echo "empty reference download: $1" >&2
            rm -f "$temp"
            return 1
        fi
        if [ -n "$expected" ] && ! verify "$temp" "$expected"; then
            echo "reference checksum mismatch: $1" >&2
            rm -f "$temp"
            return 1
        fi
        mv -f "$temp" "$1"
    else
        status=$?
        rm -f "$temp"
        return "$status"
    fi
}
# Compare cached and downloaded bytes with the immutable official-source digest.
verify() {
    printf '%s  %s\n' "$2" "$1" | shasum -a 256 -c - >/dev/null 2>&1
}
pids=()
get Comfortaa.ttf            "$B/comfortaa/Comfortaa%5Bwght%5D.ttf" &
pids+=("$!")
get Poppins-Bold.ttf         "$B/poppins/Poppins-Bold.ttf" &
pids+=("$!")
get VarelaRound.ttf          "$B/varelaround/VarelaRound-Regular.ttf" &
pids+=("$!")
get "Baloo2[wght].ttf"       "$B/baloo2/Baloo2%5Bwght%5D.ttf" &
pids+=("$!")
get MPLUSRounded1c-Bold.ttf  "$B/mplusrounded1c/MPLUSRounded1c-Bold.ttf" &
pids+=("$!")
while IFS=$'\t' read -r filename digest url; do
    [[ -z "$filename" || "$filename" == \#* ]] && continue
    get "$filename" "$url" "$digest" &
    pids+=("$!")
done < "$manifest"
status=0
for pid in "${pids[@]}"; do
    wait "$pid" || status=1
done
[ "$status" -eq 0 ] || exit "$status"
find . -maxdepth 1 -name '*.ttf' -type f | wc -l | xargs echo "reference fonts:"
