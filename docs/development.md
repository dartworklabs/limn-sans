# Development and research guide

This guide preserves the bilingual **0.100 `full` development profile** and the
brand/engine research workflow. Its Hangul, core/ext subsets, optical cuts, logo
experiments and build commands are development tools, not features or installation
instructions for the downloadable 1.002 release. Generated previews reflect their
local inputs; they are not release proofs. The brand drawing also uses its own
Quicksand Bold reference, separate from the nine release weights.

For installation, use the [1.002 release package](https://github.com/dartworklabs/limn-sans/releases/tag/v1.002)
and the [release install guide](release-install.md). That package has 919 Unicode
codepoints, 933 glyphs per face, nine static weights, and no Hangul or logo glyphs.
The [release profile](release-profile.md) documents its isolated build and checks.

The retained rules and full-profile checks below describe development intent;
they do not certify Hangul for release or resolve outstanding research findings.
Historical specifications and experiments remain under their original scope.

## 규칙

| 규칙 | 내용 |
|---|---|
| 핀 | 모든 점은 같은 원(핀)이다. 기본은 먹색이고, 주홍은 limn 앱 안에서만 쓴다. 쉼표 머리는 핀이 아니라 글자의 일부(늘 먹색) |
| 세로 | l 윗끝 = 어센더 740, 대문자 700, 디센더 −200 — 모든 굵기에서. i 핀 윗끝 = 어센더는 브랜드 그림(획 120)과 800–900. 가는 쪽은 핀 아래 흰 틈이 다른 핀들의 틈 규칙(GAP)을 넘지 않아 핀이 내려옴(100에서 윗끝 660.7) |
| 어깨 없는 n | n은 u를 180° 돌린 것, m은 n 둘(속공간만 좁힘), h는 l에 n |
| 끝과 이음 | 자유 끝과 이음은 둥글게, 기준선에 홀로 서는 세로획만 평평한 발 |
| 굵기 | 곡선 HALF: 400의 글자 회색을 곡선 D와 Inter·Pretendard 400의 중간에 두고, 900(획 155)까지 고른 간격 — 39.5 · 51.2 · 63.2 · 75.9 · 88.9 · 102.6 · 116.8 · 134.7 · 155. 이전 곡선 D(20 … 136.5)는 `LIMN_WCURVE=D`로 계속 만들 수 있음. 브랜드 그림은 Quicksand Bold(획 120) |
| 따옴표 | “ ” „의 두 핀 사이 흰 폭은 0.45 s와 0.13 x높이 중 큰 쪽(400에서 68 u). 작은 크기 컷은 여기에 1.25 px 하한 |
| 기호 | 부류마다 높이·위치·굵기 규칙: 대문자·숫자 높이, 괄호 띠, 수학 축(306.5), 위첨자, 분수. 대시·연산자·화살표의 막대 T = 줄기 S |
| 부호 | 악센트 획 = 줄기 × 0.87, 모든 굵기에서 같은 비. 막대 글자(Đ Ħ Ŧ đ ħ ŧ)의 막대는 화폐 막대와 같은 LIGHT 펜, 줄기 밖으로 둥근 끝 + 0.45 s, đ ħ는 줄기 끝이 막대 위로 0.8 s 드러남. 결합 부호(U+0300–0328)는 폭 0 |
| 흰 공간 | 글자가 가둔 흰 공간(속공간)은 모든 굵기에서 0.35 s 이상 — 좁아지면 둘레의 먹을 깎음(최대 0.12 s). 표시가 가르는 흰 공간은 0.4 s 이상(₦ ₭ ₱) |
| 간격 | Walter Tracy 방식 — 옆여백 = 글자 모양 부류 비율 × o(대문자 O)의 옆여백, 예외만 커닝 |
| 숫자 | 고정폭과 비례 두 가지(조판 옵션 `tnum`). 폰트 파일은 고정폭이 기본이고 `pnum`이 비례 숫자 — 문장 속 숫자(고정폭 1은 셀의 흰 폭이 넓음)는 `pnum`으로(아래 CSS). 고정폭 숫자는 서로, 그리고 글자와 커닝하지 않고, 뒤의 따옴표·프라임과 위 부호만 벌림. 위첨자 ¹과 아래첨자 ₁은 비례 1 |
| 한글 | 나눔스퀘어라운드(L·R·B·EB). 브랜드 기준점(곡선 A의 400·700)은 R × 0.8901 · EB × 0.8708, 틀 중심은 기준선 위 350(cap/2), 틀 − 획/2 일정(잉크 틀을 굵기와 무관하게 유지). 획 = 라틴 S × 0.95(400 이하)–0.93(900)을 기준으로, 교정 음절의 먹이 S에 대한 한 이차식을 따르도록 굵기마다 ±5 % 안에서 다시 풂(마스터가 바뀌는 자리에서 먹이 되돌아가지 않게). 굵기마다 획이 가장 가까운 마스터 + 둥근 펜(GEOS/shapely): 가는 쪽은 부분마다 깎기, 굵은 쪽은 조각마다 한 펜으로 불리되 자모 사이 흰 틈 0.3 S·속공간 0.3 S를 모든 굵기에서 지킴(부모가 이미 더 가까우면 둥근 끝 쪽을 잘라 맞춤), ㅅ ㅈ ㅊ의 뾰족한 가랑이는 필렛. 펜 결과는 TrueType 2차 곡선으로 다시 맞춤(부모 곡선점을 힌트로, 편차 1단위 이내, 수직·수평 획은 정확히 수직·수평). 굵기(곡선 HALF)별 마스터: 100–200 L, 300–400 R, 500–600 B, 700–900 EB. 현대 한글 11,172자 전부(나눔스퀘어라운드가 그리지 않은 8,693자는 그린 음절의 자모로 조합) + 낱자 ㄱ–ㅣ + 한국어 문장부호와 기호(ㆍ・～ ○●□■△▲☆★ ℃ ㎡㎏㎝㎞ ①–⑩ ▶▷▼▽◀◁◆◇♠♡♥♣♪☎). 괄호·도형 기호는 R 하나에서 굵기에 묶인 둥근 펜으로, ㎏㎝㎞㎡ ℃ ①–⑩은 Limn의 글자·숫자로 조합. 엔진 데이터는 KS X 1001 2,350자·낱자·기호(`limn-hangul-<w>.js`)와 나머지 8,822자(`limn-hangulext-<w>.js`, 쓰일 때만 불러옴)로 나눔 |
| 한글 간격 | 글자마다 모든 굵기에서 한 너비: 나눔스퀘어라운드 R의 너비 × 400의 배율(0.8952), 음절은 815. 굵기마다 잉크를 그 안 가운데에 둠 (굵기를 바꿔도 줄 길이가 그대로). 라틴 \| 한글 경계는 더하지 않음(가장 가까운 먹 거리로 이미 참고 서체와 같음), 커닝 없음 |
| 림 | 나눔스퀘어라운드의 림에서 ㅣ를 i로 — 핀 지름 = 줄기 = ㅣ 굵기, 틈 0.35 × 굵기, 핀 윗끝 = ㅣ 윗끝, 줄기 끝 = ㅣ 끝. 핀은 엔진이 그림(로고 주홍, 본문 먹). 폰트 파일의 림은 핀 없는 음절. 핀 꽂힌 로고 림은 나눔스퀘어라운드 윤곽을 그대로 쓰므로, TTF에 담기면 상표 권리와 무관하게 그 글리프도 OFL 1.1 §5에 따라 OFL로만 배포해야 한다. 그래서 현재 릴리스 파일에는 넣지 않았다(`LIMN_TTF_LOGO=1`이면 `ss02`로 들어감, 내부용) |

## 빌드

```sh
make refs    # 비교용 참고 서체(OFL, Google Fonts·Pretendard) — pages에만 필요
make all     # 100–900, 작은 크기 컷, 폰트 뒤 페이지·커버리지 데이터 생성 (오래 걸림)
make font    # 700만
make hangul  # 한글 100–900 → site/limn-hangul-<w>.js (나눔스퀘어라운드를 NAVER에서 받아 SHA-256 확인)
make hangul-measure  # 굵기별 한글 수치 → site/hangul-measure.js (hangul.html)
make check   # tools/audit.py(모든 굵기·컷의 글자 게이트와 curve: 기본 S = HALF 표, 400에서 “ 흰 폭 0.13 x높이 — 아래 품질 범위는 실패, 그 밖은 info, #20)
             # 그리고 tools/audit_hangul.py(음절 11,172자, 한 너비, 곡선, 조각·구멍 불변, 속공간·흰 틈 0.3 S, 먹 단조 증가, 수직·수평,
             # parent-ink: 음절의 먹 ÷ 가의 먹이 그 굵기 마스터의 같은 비의 0.5 미만이면 실패, 0.8 미만은 보고)
make test    # site/tools의 단위 테스트(빌드 데이터 없이 돈다, 나눔스퀘어라운드만 받아 둔다) — CI도 이것을 돌린다
make quality # 새 캐시·미리보기·커버리지 도구에 한정한 Ruff 포맷/린트와 mypy — CI도 이것을 돌린다
make coverage-page # 기존 아홉 TTF와 참고 서체의 실제 cmap·렌더로 site/coverage.html 재생성
make pages   # 기존 아홉 TTF 필요: 참고 서체·페이지 데이터와 커버리지 생성
make fonts   # 폰트 파일 100–900 → site/fonts/ (play·hangul 다음), 만든 뒤 데이터와 대조
make fonts-page  # fonts.html을 Chromium으로 열어 엔진 줄과 @font-face 줄을 잰다 (Playwright)
make icons   # 앱 아이콘 PNG(16·20·32·40·64, 1×·2×, 뼈종이·먹), 브라우저 파비콘(먹, favicon-16·32.png·favicon.ico), apple-touch-icon(180, 꽉 찬 네모),
             # 벡터 아이콘·Limn 앱이 인라인하는 SVG(아이콘 14·16, 워드마크 20)와 SHA256SUMS → site/icons/ (Playwright, Pillow)
```

`make play`는 아홉 굵기를, `make cuts`는 네 컷의 아홉 굵기(36번)를 한꺼번에 굽는다(`LIMN_JOBS`가 컷마다 동시에 도는 굵기 수를 정함).

`make check`의 품질 범위는 한국어·영어와 문장부호, 숫자 위·아래첨자와 부호, Currency Symbols(U+20A0–20CF)·Letterlike Symbols(U+2100–214F)·Number Forms(U+2150–218F)·Arrows(U+2190–21FF)·Mathematical Operators(U+2200–22FF)·Miscellaneous Technical(U+2300–23FF) 블록 전체, 기존 원문자·도형·기타 기호와 명시한 보충 기호 `⟨⟩⟵⟶⟷✓✔✗✘`다. 그리스어·확장 라틴과 `ₑ` 같은 알파벳 첨자는 계속 정보로만 보고한다. 이는 기존 기호 계약을 복구하는 범위이며, 비공개 이력의 언어 커버리지 과제의 언어 확장을 완료했다는 뜻은 아니다.

브라우저가 직접 쓰는 비교 서체 Quicksand·Nunito·Fredoka와 OFL 문서는 `site/tools/comparison_refs.tsv`의 공식 커밋 URL·SHA-256으로 고정한다. `make refs`는 기존 파일도 해시를 확인하고, 완료한 다운로드만 원자적으로 채택한다. `make preview`는 이 세 서체와 라이선스를 함께 복사해 비교 페이지의 실제 파일을 보존한다.

`make coverage-page`는 기존 아홉 굵기 TTF와 Inter·Pretendard·Noto Sans KR의 실제 cmap을 읽어 문자 수와 유니코드 블록별 범위를 낸다. `make pages`에도 포함되며, `make all`은 폰트 생성 뒤 페이지를 마지막으로 만든다. 대표 글자 PNG를 페이지에 넣으므로 열람할 때 참고 서체를 내려받지 않는다. `uv run --no-project --with fonttools python3 site/tools/build_coverage_page.py --report-only`는 브라우저 없이 같은 범위 보고서를 만든다. `site/figures/manifest.json`이 있으면 함께 대조하며, `--manifest PATH`로 필수 대조 파일을 지정할 수 있다.

Python은 `uv`로 돈다(`uv run --no-project --with skia-pathops --with fonttools --with uharfbuzz --with shapely`, 한글은 `numpy`·`pillow`도, 폰트 파일은 `brotli`도). 결과는 `site/`에 생기고, `site/*.html`을 정적 서버로 연다.

`make hangul`은 각 글자의 요청한 모든 굵기를 함께 만든 뒤 `site/tools/hangul/.glyph-cache/`에 저장한다. 음절·낱자·기호 모두 대상이며, 곡선 데이터·너비·상자와 먹 조정(held) 기록을 보존한다. 입력이 같은 글자는 다시 맞추지 않고 읽는다. 글자 하나가 끝날 때마다 원자적으로 저장하므로 중단 후에도 완료한 글자를 재사용한다. 100자마다 완료 수·재사용/신규 수·경과 시간·남은 시간 추정을, 마지막에는 합계를 출력한다. 같은 키를 동시에 만드는 프로세스는 파일 잠금으로 한 번만 계산한다. 깨졌거나 불완전한 기록은 누락으로 취급한다. 캐시 폴더는 지워도 된다.

키에는 요청 굵기의 순서, 실제 짝짓기 값 전체(기호가 쓰는 400 포함), 한글 생산·검사·맞춤·직렬화 코드, 부모 TTF 네 개, 라틴 `limn-font-play.js`, 설치한 Python·수치/기하 의존성의 실제 코드와 네이티브 파일, 규칙 환경 변수가 들어간다. `.params-cache.json`의 먹 평활화 값도 코드·부모·의존성 변경으로 자동 무효화된다. 빌드 중 입력을 바꾸면 결과를 채택하지 않는다. 코드가 바뀌어도 펜 윤곽이 같은 글자만 골라 맞춤을 재사용하는 최적화는 비공개 이력의 캐시 후속 과제의 후속 단계다. 현재 단계는 입력이 완전히 같은 재빌드와 중단 복구다.

`LIMN_KO_CACHE=0 make hangul`은 글리프 캐시와 기존 짝짓기 디스크 캐시의 읽기·쓰기를 모두 끈다. 먹 평활화 규칙은 그대로 계산한다. 릴리스 전에는 이 전체 빌드와 캐시 빌드의 JS 바이트를 대조하고 `make check`를 통과시켜야 한다. 빠른 개발 대조는 `LIMN_KO_CHARS='가갂ㄱ○' LIMN_KO_OUT=/tmp/limn-hangul-probe make hangul`처럼 실제 문자 부분집합으로 할 수 있다. 전체 결과를 덮지 않도록 부분집합은 `site/` 밖 출력 경로가 필수다. `LIMN_KO_CACHE_DIR`은 실험용 별도 캐시 폴더를 지정한다. 기본 문자 범위·출력 위치는 바뀌지 않는다.

`make figures`가 부르는 `tools/check_figures.py`는 내보낸 그림에 공개하면 안 되는 문자열이 섞였는지 본다. 일반 패턴(`/home/`, `~/`, `/tmp/`, `@gmail.com`)만 소스에 있고, **그 기기·조직의 고유한 비공개 이름(내부 호스트, 프로젝트 코드네임)은 `site/tools/private-strings.txt`에 한 줄에 하나씩 적는다.** 이 파일은 커밋하지 않는다 — 공개 저장소가 막으려는 문자열을 스스로 담고 있으면 안 되기 때문이다. 이름을 하나도 읽지 못하면(파일이 없거나, 비었거나, 주석뿐이면) 검사는 조용히 넘어가지 않고 **실패**한다. 감출 것이 없는 복제본에서는 `LIMN_PRIVATE_STRINGS=none`으로 일반 패턴만 검사하겠다고 명시한다.

## 폰트 파일

첫 릴리스의 명시적 입력·패키징·검증 절차는 [릴리스 프로필](release-profile.md), 배포본에 넣을 설치·품질 범위 설명은 [설치 안내](release-install.md)를 따른다. `make fonts-release`는 한글 전체 데이터 없이 기존 라틴과 새 기호 전용 입력으로 힌팅된 TTF 9개·WOFF2 9개를 만든다. 기본 `make fonts`의 한영 개발 동작과 아래 core/ext 계약은 유지한다.

`make fonts`가 굵기마다 `site/fonts/LimnSans-<이름>.ttf`와 `.woff2`를 만든다 — Thin 100, ExtraLight 200, Light 300, Regular 400, Medium 500, SemiBold 600, Bold 700, ExtraBold 800, Black 900. 빌드 산출물이라 저장소에는 넣지 않는다.

웹용으로 `LimnSans-<이름>-core.woff2`(현대 한글 음절 이외의 모든 문자 + KS X 1001 음절 2,350자)와 `-ext.woff2`(나머지 음절 8,822자), `site/fonts/fonts.css`도 만든다. 페이지에서 `<link rel="stylesheet" href="fonts/fonts.css">`로 연결하면 CSS의 서로 겹치지 않는 `unicode-range`에 따라 필요한 파일을 불러온다. CSS와 두 WOFF2를 같은 폴더에 둔다. 원래의 전체 TTF·WOFF2는 그대로 제공하며, 서브셋은 이름·OFL 문구·힌팅과 적용 가능한 OpenType 대체 글자·커닝을 보존한다. `check_ttf.py`는 두 cmap의 교집합이 비고 합집합이 전체 폰트와 같은지, 음절 수와 CSS 범위, 보존한 글자·메타데이터·조판을 검사한다.

`LIMN_TTF_OUT`은 폰트 출력 폴더, `LIMN_TTF_HANGUL_IN`은 한글 JS 입력 폴더(`LIMN_KO_OUT`도 입력 기본값으로 받음), `LIMN_TTF_PLAY_IN`은 라틴 JS 입력 파일을 지정한다. 예를 들어 `LIMN_TTF_HANGUL_IN=/tmp/limn-half-data LIMN_TTF_OUT=/tmp/limn-half-fonts make fonts`는 기존 라틴 데이터와 HALF 한글을 읽어 별도 폴더에 만들므로 `site/`의 입력 데이터를 덮지 않는다.

폰트는 Quicksand가 아니라 조판 엔진의 데이터(`limn-font-play.js`, `limn-hangul-<w>.js`)에서 굽는다. 브라우저가 이 파일로 짠 줄과 엔진(`LIMN_playset`, 기본 규칙)이 짠 줄이 같아야 하기 때문이다.

| 항목 | 폰트에서 |
|---|---|
| 핀 | 엔진은 점을 윤곽 위에 원으로 그린다. 폰트는 한 가지 색이라 핀을 먹 원으로 윤곽에 합친다(skia-pathops). 주홍 핀은 limn 앱 엔진에만 있다 |
| 윤곽 | TrueType 2차 곡선(cu2qu, 허용 오차 0.5 단위), 겹침 제거, 바깥 윤곽 시계 방향. 정수 격자에 맞추기 전후로 1 단위² 미만 윤곽, 길이 0 선분·겹친 점, 되돌아가는 점(폭 0 가시·들쭉날쭉한 모서리)을 뺌 |
| 커닝 | 엔진의 `kernOf` — 쌍이 없으면 두 커닝 부류의 기준 쌍. GPOS `kern`: 부류 쌍(PairPos 2) + 부류와 다른 쌍(PairPos 1, 먼저 찾음) |
| 숫자 | 기본은 고정폭(엔진의 `tnum`). `pnum`은 비례 숫자와 그 커닝(`pkern`), `tnum`은 되돌림 |
| 대체 글자 | `ss01` 두 층 a g, `zero` 점 있는 0 — 엔진의 스위치와 같은 글자. 로고 림(`ss02`)은 `LIMN_TTF_LOGO=1` 빌드에만 |
| 공백 | 엔진의 `spaceOf`와 같음: U+00A0 = 단어 공백, U+2009·U+202F = 부모의 thin 공백(205), U+2002·U+2003 = en·em, U+3000 = 그 굵기 가의 폭, U+00AD·U+200B = 폭 0(앞뒤 짝의 커닝은 이어짐) |
| 한글 | 라틴 데이터에 없는 글자는 같은 굵기의 한글 데이터에서. 라틴 \| 한글 경계 흰 폭(`bnd`)은 지금 모든 굵기에서 0 |
| 줄 상자 | typo = hhea = win: 어센더 970, 디센더 −330, 줄 간격 0, USE_TYPO_METRICS — 기본 줄 높이 1.3 em, 모든 굵기의 모든 글자가 안에 든다(라틴 740/−200 위아래로 230·130, 가장 높은 Å 968, 가장 깊은 Ģ −327, 한글 약 765/−60) |
| 이름 | 패밀리 "Limn Sans", 400·700은 Regular·Bold, 나머지는 "Limn Sans <이름>" + 16/17번 이름. 저작권·OFL 문구와 URL, 상위 예약 이름(Quicksand · NAVER). Limn Sans 자체는 예약 이름을 두지 않는다 |
| 힌팅 | TTF는 저장 직후 ttfautohint(ttfautohint-py)로 제자리 힌팅하고, 그 파일에서 `.woff2`를 깎는다 — 작은 크기에서 획을 픽셀 격자에 맞춘다. 라틴·기호는 `latn` 스크립트로 정식 힌팅. 한글과 KS X 1001 기호는 ttfautohint에 스크립트 모듈이 없어(`--help`의 스크립트 표에 hang·hani 없음) fallback 경로로 빠지는데, 기본값(스크립트 없이도 힌팅)은 11–16px에서 을 같은 조밀한 음절의 가로 획 3개가 같은 픽셀 행에 뭉쳐 속공간이 까맣게 막히는 게 굵기 전반에서 재현됐다. `fallback_scaling`(힌팅 대신 스케일)으로 바꾸면 라틴 힌팅은 그대로 두고 한글만 무힌팅 대조군과 같은 결로 나와 그쪽을 택했다(FreeType 렌더 비교, 아래 표 옆 검증 참고). `LIMN_TTF_HINT=0 make fonts`가 이 단계를 건너뛴다(파일이 더 작지만 작은 크기에서 획이 덜 또렷하다). 힌팅한 파일은 `head.flags` 3번 비트(PPEM 정수)를 켠다 |

`tools/check_ttf.py`(make fonts가 이어서 돌림)가 파일마다 cmap이 두 데이터의 글자를 모두 덮는지, 매핑된 글자에 빈 글리프가 없는지, 폭이 엔진의 폭인지, 핀이 제자리에 있는지, HarfBuzz로 짠 커닝이 `kernOf`·`pkern`과 같은지, 교정 문장의 줄 끝이 엔진과 같은지, (힌팅이 켜졌으면) `fpgm`/`prep`과 글리프 바이트코드가 있는지 확인한다. `fonts.html`은 굵기마다 엔진 줄 바로 아래에 @font-face 줄을 놓고(겹쳐 보기 가능) 줄 끝·먹 폭·픽셀 차를 잰다. `make fonts-page`가 그 페이지를 Chromium으로 열어 수치와 스크린숏을 남긴다.

```css
@font-face { font-family: "Limn Sans"; font-weight: 400; src: url("LimnSans-Regular.woff2") format("woff2"); }
.pnum { font-variant-numeric: proportional-nums; }   /* 숫자는 기본이 고정폭 */
```

## 구조

- `site/tools/build_font.py` — Quicksand 한 굵기를 받아 limn 규칙을 입혀 글자 데이터를 만든다
- `site/tools/weights.py` — 굵기 100–900 (300–700 안은 Quicksand 인스턴스, 밖은 펜으로 깎고 불림)
- `site/tools/punct.py` — 구두점·기호 체계, `accents.py` — 악센트 글자와 결합 부호, `greek.py` — 그리스 문자, `sym_math.py` · `sym_numeric.py` — 수학·화살표·키보드, 위첨자·분수·화폐, `spacing.json` — 간격 부류, `geom.py` — 빌드가 재는 흰 공간과 윤곽 위생(shapely)
- `site/tools/audit.py` — `make check`의 게이트: 데이터, 굵기 사이 윤곽·속공간 개수, 속공간 0.3 s, 굵기마다 먹이 늘어남, 가시·틈·티끌, 커닝 범위, 악센트 획 0.83–0.92 s, 실제 문자열(`audit_pairs.txt`와 교정 문장)의 이웃 먹 거리 0.1 s, 한글
- `site/tools/hangul.py` — 한글 짝짓기 규칙(마스터·펜·배율·기준선·너비·경계)·조합·곡선 맞춤과 림, `build_hangul.py` — 굵기별 한글 데이터(모든 굵기를 한 풀에서), `hangul_cache.py` — 같은 입력의 글자별 기록·중단 복구, `audit_hangul.py` — 한글 게이트, `hangul_measure.py` — 만든 데이터를 다시 재는 검증, `fetch_hangul.sh` — 나눔스퀘어라운드 내려받기
- `site/limn-brand.js` — 조판 엔진(`LIMN_playset`, 커닝 클래스, 핀, 한글 대체와 `LIMN_loadHangul`)과 앱 아이콘(`icon`; 16·20·24·32px는 픽셀 격자에 따로 그린 `ICON_PX`), 브라우저 파비콘(`favicon`; 16·32px 먹 픽셀 그림 `FAVICON_PX`)
- `site/tools/build_icons.py` — 아이콘 PNG·파비콘·.ico·apple-touch-icon을 Chromium으로 그 크기에 래스터하고 SVG를 쓴 뒤 확인한다: 핀과 획 사이 틈, 파비콘이 정사각을 채우는지, .ico 프레임, 터치 아이콘의 불투명·순서, SVG의 색(주는 핀에만)·광학 보정·핀 아래 1.25px, SHA256SUMS
- `site/tools/build_ttf.py` — 엔진 데이터를 폰트 파일로, `check_ttf.py` — 파일을 데이터와 대조, `check_fonts_page.py` — fonts.html을 Chromium에서 재기
- `site/*.html` — 서체·교정쇄·구두점·굵기·기호·자간·악센트·폰트 파일·작은 아이콘(`icons.html`) 페이지

산출물은 웹 페이지용 윤곽 데이터(JS)와 그 데이터로 구운 폰트 파일(`site/fonts/`)이다. 첫 1.000은 명시적 릴리스 프로필로 별도 패키지를 만든다. Google Fonts 저장소 구조(`sources/`, `fonts/`)로의 이전은 이번 범위에 포함하지 않는다.

## 라이선스

글꼴과 글꼴 데이터는 [SIL Open Font License 1.1](../OFL.txt). Quicksand(© The Quicksand Project Authors)와 나눔스퀘어라운드(© NAVER Corporation, [라이선스 원문](../site/tools/hangul/OFL-NanumSquareRound.txt))의 수정판이므로 "Quicksand"와 NAVER의 예약 이름("Nanum"과 그 변형 전부)을 쓰지 않는다. Limn Sans 자체는 예약 이름을 두지 않으므로 고친 판도 같은 이름으로 낼 수 있다 — 이름과 마크를 지키는 것은 라이선스가 아니라 아래의 상표다. 나눔스퀘어라운드 TTF(4.1 MB)는 저장소에 넣지 않고 `make hangul-fonts`가 NAVER의 배포 zip에서 받는다. limn의 로고·워드마크는 README용 사본이 `docs/assets/brand/`에만 있고, Dartwork의 상표라서 이 라이선스로 제공되지 않는다. 다만 나눔스퀘어라운드 윤곽에서 온 글리프는 폰트 파일에 담기는 순간 상표와 무관하게 OFL 1.1(§5)을 따른다.
