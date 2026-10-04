import type { components } from "@/lib/api";
import { formatMonthDay, formatPercent, formatWon } from "@/lib/format";
import type { MarketInfo } from "@/lib/markets";
import { tone } from "@/lib/summary";

type NextOpen = components["schemas"]["NextOpenOut"];

const pct = (value: string | null) => (value === null ? "—" : formatPercent(Number(value)));
const rate = (value: string | null) =>
  value === null ? "—" : `${Number(value).toLocaleString("ko-KR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}원`;

// 국내 장이 닫힌 뒤 미국장·환율 변동을 반영한 다음 개장 추정 — 토스에서는 국내 종가만 보임
export function NextOpenCard({ info, data }: { info: MarketInfo; data: NextOpen }) {
  if (data.state === "kr_open" || data.estimate === null || data.kr_close === null || data.kr_close_day === null) {
    return (
      <section className="space-y-1 rounded-2xl bg-subtle p-5">
        <p className="text-sm text-muted">다음 개장 예상 · {info.name}</p>
        <p className="font-semibold">한국장이 열려 있어요</p>
        <p className="text-xs text-muted">장이 끝나면(15:30) 그 뒤 미국장·환율로 다음 개장가를 추정해요.</p>
      </section>
    );
  }

  const change = Number(data.change);
  const holdings = data.basis === "holdings";

  return (
    <section className="space-y-4 rounded-2xl bg-subtle p-5">
      <p className="text-sm text-muted">다음 개장 예상 · {info.name}</p>

      <div className="grid grid-cols-2 divide-x divide-border rounded-xl bg-background">
        <div className="space-y-1 px-4 py-4">
          <p className="text-xs text-muted">{formatMonthDay(data.kr_close_day)} 종가</p>
          <p className="text-xl font-bold tabular-nums">{formatWon(Number(data.kr_close))}</p>
        </div>
        <div className="space-y-1 px-4 py-4">
          <p className="text-xs text-muted">{formatMonthDay(data.next_open_day)} 개장 예상</p>
          <p className="text-xl font-bold tabular-nums">약 {formatWon(Math.round(Number(data.estimate)))}</p>
          <p className={`text-sm font-semibold tabular-nums ${tone(change)}`}>{formatPercent(change)}</p>
        </div>
      </div>

      <ul className="divide-y divide-border text-sm">
        <li className="flex items-baseline justify-between gap-3 py-2">
          <span className="text-muted">
            {holdings ? "구성 종목 (비중 가중)" : `미국 ${data.legs[0]?.symbol ?? ""}`}
            {data.us_reference_day && data.us_latest_day && (
              <span className="ml-1 text-xs">
                · 뉴욕 {formatMonthDay(data.us_reference_day)} → {formatMonthDay(data.us_latest_day)} 종가
              </span>
            )}
          </span>
          <span className={`shrink-0 font-medium tabular-nums ${tone(Number(data.basket_change))}`}>
            {pct(data.basket_change)}
          </span>
        </li>
        <li className="flex items-baseline justify-between gap-3 py-2">
          <span className="text-muted">
            원/달러
            <span className="ml-1 text-xs">
              · {rate(data.fx_reference)} → {rate(data.fx_latest)}
            </span>
          </span>
          <span className={`shrink-0 font-medium tabular-nums ${tone(Number(data.fx_change))}`}>
            {pct(data.fx_change)}
          </span>
        </li>
      </ul>

      {holdings && data.legs.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-xs text-muted">구성 종목 · 비중 순</p>
          <ul className="space-y-1">
            {data.legs.map((leg) => (
              // 마우스를 올리면(폰은 누르면) 회사 이름 — 클릭 포커스로는 남지 않게 키보드 포커스만 유지
              <li
                key={leg.symbol}
                tabIndex={0}
                className="group relative grid grid-cols-[3.5rem_1fr_auto] items-center gap-2 rounded text-xs tabular-nums outline-none hover:bg-background/60 focus-visible:bg-background/60"
              >
                <span className="font-medium">{leg.symbol}</span>
                <span
                  role="tooltip"
                  className="pointer-events-none absolute top-1/2 left-14 z-10 hidden -translate-y-1/2 whitespace-nowrap rounded-md bg-foreground px-2 py-0.5 text-[11px] text-background shadow group-hover:block group-focus-visible:block"
                >
                  {leg.name}
                </span>
                <span className="flex items-center gap-2">
                  <span className="h-1.5 rounded-full bg-muted/40" style={{ width: `${Number(leg.weight) * 100 * 2}%` }} />
                  <span className="text-muted">{(Number(leg.weight) * 100).toFixed(1)}%</span>
                </span>
                <span className={tone(Number(leg.change))}>{formatPercent(Number(leg.change))}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {data.us_pending && (
        <p className="rounded-lg bg-background px-3 py-2 text-xs text-muted">
          {formatMonthDay(data.next_open_day)} 개장 전에 미국장이 한 번 더 열려요 — 그 장이 끝나면 값이 바뀌어요.
        </p>
      )}

      <p className="text-xs leading-relaxed text-muted">
        추정치예요. 미국은 확정된 정규장 종가만, 환율은 매매기준율로 계산했어요.
        {holdings
          ? " 비중은 운용사가 공개한 최신 구성 종목이에요."
          : ` 같은 지수를 따르는 ${data.legs[0]?.symbol ?? "미국 ETF"}로 근사했어요.`}
        {Number(data.coverage) < 0.995 &&
          ` 구성 종목 중 ${((1 - Number(data.coverage)) * 100).toFixed(1)}%는 시세를 못 받아 빼고 계산했어요.`}{" "}
        한국 장중에 이미 반영된 미국 선물 움직임, 괴리율 때문에 실제 시가와 다를 수 있어요.
      </p>
    </section>
  );
}
