#!/usr/bin/env bash
# NanumSquareRound L R B EB, the parent of Limn Sans' Hangul (NAVER, SIL OFL 1.1 — tools/hangul/OFL-NanumSquareRound.txt).
# The four TTFs are 4.1 MB, so they are fetched rather than committed: NAVER's own zip from its font CDN
# (the one hangeul.naver.com serves), checked against the SHA-256 of the files the pairing was measured on.
set -euo pipefail
D="$(cd "$(dirname "$0")" && pwd)/hangul"
URL=https://hangeul.pstatic.net/hangeul_static/webfont/zips/nanum-square-round.zip
declare -A SHA=(
  [NanumSquareRoundL.ttf]=b0bd9e7e067840d55520ce7e45a3e57327144da136b4ab558fb98b200701d071
  [NanumSquareRoundR.ttf]=52862fdf05b55ba886ca21998222d9598ef84c975e68046b9a8d8f1af09228a0
  [NanumSquareRoundB.ttf]=61fd37816a1ee1a9336876742392d80bdafd340e5124a088aeda20446e2e15de
  [NanumSquareRoundEB.ttf]=9e845fc35c5bc4a5b7ed59d85a1760059de5ce55b5e5a4d7535f7efa87695e39
)
ok() { for f in "${!SHA[@]}"; do [ -s "$D/$f" ] && echo "${SHA[$f]}  $D/$f" | sha256sum -c --quiet - 2>/dev/null || return 1; done; }
if ok; then echo "NanumSquareRound: present"; exit 0; fi
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
curl -fsSL --connect-timeout 5 --max-time 120 -o "$T/nsr.zip" "$URL"
unzip -q -o "$T/nsr.zip" 'NanumSquareRound*.ttf' -d "$T"
for f in "${!SHA[@]}"; do
  echo "${SHA[$f]}  $T/$f" | sha256sum -c --quiet - || { echo "checksum mismatch: $f (NAVER changed the zip?)" >&2; exit 1; }
  cp "$T/$f" "$D/$f"
done
echo "NanumSquareRound: fetched from $URL"
