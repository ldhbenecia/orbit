#!/usr/bin/env bash
# 필요할 때만 로컬 대시보드를 띄움 — 시세 갱신 → 엔진 API(8000) + 웹(3000) → 브라우저
# Ctrl+C 한 번에 둘 다 종료. 시세 갱신을 건너뛰려면 --no-sync
set -euo pipefail
cd "$(dirname "$0")/.."

ENGINE_PORT=8000
WEB_PORT=3000
URL="http://localhost:${WEB_PORT}"

for port in "$ENGINE_PORT" "$WEB_PORT"; do
  if lsof -ti "tcp:${port}" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "포트 ${port} 이 이미 쓰이고 있어요 — 켜 둔 엔진·웹을 먼저 끄세요 (lsof -ti tcp:${port} -sTCP:LISTEN)" >&2
    exit 1
  fi
done

[ -d web/node_modules ] || pnpm --dir web install --frozen-lockfile

if [ "${1:-}" != "--no-sync" ]; then
  echo "▶ 시세 갱신"
  uv run --project engine orbit sync-candles --market KRW-BTC
  uv run --project engine orbit sync-candles --market KRW-ETH
  # 허용 IP 가 아닌 곳(카페 등)에서는 토스가 막힘 — 코인은 그대로 볼 수 있게 계속 진행
  uv run --project engine orbit sync-stocks || echo "  토스 시세 갱신 실패 — 허용 IP 확인. 미국주식·ETF 는 마지막 받은 데이터로 보여요"
  uv run --project engine orbit validate >/dev/null 2>&1 || echo "  규칙 검증 갱신 실패 — 마지막 결과로 보여요"
fi

# 이 스크립트가 띄운 프로세스 전부(웹 자식 프로세스 포함)를 같이 끔
trap 'trap - EXIT; echo; echo "■ 종료"; kill 0' EXIT INT TERM

echo "▶ 엔진 API :${ENGINE_PORT}"
# 정상 요청 기록(200 OK)은 숨기고 경고·오류만 보이게
uv run --project engine orbit serve --port "$ENGINE_PORT" 2>&1 | grep --line-buffered -v '" 200 OK$' &
echo "▶ 웹 :${WEB_PORT}"
pnpm --dir web dev --port "$WEB_PORT" >/dev/null &

for _ in $(seq 1 60); do
  curl -s -o /dev/null "$URL" && break
  sleep 1
done
echo "● ${URL} — 끄려면 Ctrl+C"
command -v open >/dev/null && open "$URL"
wait
