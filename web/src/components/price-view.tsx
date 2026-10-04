"use client";

import { useMemo, useState } from "react";

import { CandleChart, type ChartMarker } from "@/components/candle-chart";
import type { components } from "@/lib/api";
import type { ChartCandle, Interval } from "@/lib/candles";
import { formatDate, formatPercent, formatSignedWon, formatWon } from "@/lib/format";
import { ruleName } from "@/lib/rules";
import { type ChartTrade, groupByBar, toChartTrade } from "@/lib/trades";

type Run = components["schemas"]["RunOut"];
type TradesState = ChartTrade[] | "loading" | "error";

const INTERVALS: { value: Interval; label: string; initialBars: number | null }[] = [
  { value: "day", label: "일", initialBars: 90 },
  { value: "week", label: "주", initialBars: 78 },
  { value: "month", label: "월", initialBars: null },
];

// 단순 보유 → 이동평균(짧은 순) → 변동성 돌파
const RULE_ORDER = ["hold", "ma", "vb"];
const byRuleOrder = (a: Run, b: Run) => {
  const [an, ap] = a.strategy.split("-");
  const [bn, bp] = b.strategy.split("-");
  return RULE_ORDER.indexOf(an) - RULE_ORDER.indexOf(bn) || Number(ap ?? 0) - Number(bp ?? 0);
};

const tone = (value: number) => (value > 0 ? "text-up" : value < 0 ? "text-down" : "text-muted");

const barLabel = (day: string, interval: Interval) => {
  if (interval === "month") return formatDate(day).replace(/ \d+일$/, "");
  return interval === "week" ? `${formatDate(day)} 주` : formatDate(day);
};

type Props = {
  market: string;
  runs: Run[];
  daily: ChartCandle[];
  byInterval: Record<Interval, ChartCandle[]>;
};

export function PriceView({ market, runs, daily, byInterval }: Props) {
  const [interval, setInterval] = useState<Interval>("day");
  const [runId, setRunId] = useState<number | null>(null);
  const [tradesByRun, setTradesByRun] = useState<Record<number, TradesState>>({});
  // 막대 위치는 단위마다 다름 — 어느 단위의 위치인지 같이 저장해 단위를 바꾼 직후 옛 위치를 쓰지 않음
  const [visibleState, setVisible] = useState<{ interval: Interval; from: number; to: number } | null>(null);
  const [hoverState, setHover] = useState<{ interval: Interval; index: number } | null>(null);

  const candles = byInterval[interval];
  const option = INTERVALS.find((o) => o.value === interval)!;
  const visible = visibleState?.interval === interval ? visibleState : null;
  const hover = hoverState?.interval === interval ? hoverState.index : null;

  const last = daily[daily.length - 1];
  const prev = daily[daily.length - 2];
  const change = last.close - prev.close;

  const legend = candles[hover ?? candles.length - 1];
  const legendChange = legend.close - legend.open;

  const run = runs.find((r) => r.id === runId) ?? null;
  const tradesState = runId === null ? null : (tradesByRun[runId] ?? "loading");
  const bars = useMemo(
    () => (Array.isArray(tradesState) ? groupByBar(tradesState, interval) : new Map()),
    [tradesState, interval],
  );
  const markers = useMemo<ChartMarker[]>(
    () =>
      [...bars.entries()]
        .sort(([a], [b]) => a.localeCompare(b))
        .flatMap(([day, bar]) => [
          ...(bar.buys.length ? [{ day, side: "buy" as const, count: bar.buys.length }] : []),
          ...(bar.sells.length ? [{ day, side: "sell" as const, count: bar.sells.length }] : []),
        ]),
    [bars],
  );
  const legendTrades = bars.get(legend.day);

  const selectRun = async (id: number | null) => {
    setRunId(id);
    if (id === null || Array.isArray(tradesByRun[id])) return;
    setTradesByRun((prev) => ({ ...prev, [id]: "loading" }));
    try {
      const res = await fetch(`/api/backtests/${id}/trades`);
      if (!res.ok) throw new Error(String(res.status));
      const trades = (await res.json()) as components["schemas"]["TradeOut"][];
      setTradesByRun((prev) => ({ ...prev, [id]: trades.map(toChartTrade) }));
    } catch {
      setTradesByRun((prev) => ({ ...prev, [id]: "error" }));
    }
  };

  const stats = useMemo(() => {
    if (!visible) return null;
    const range = candles.slice(visible.from, visible.to + 1);
    return {
      from: range[0].day,
      to: range[range.length - 1].day,
      ratio: range[range.length - 1].close / range[0].open - 1,
      high: Math.max(...range.map((c) => c.high)),
      low: Math.min(...range.map((c) => c.low)),
    };
  }, [candles, visible]);

  return (
    <div className="space-y-8">
      <section className="space-y-1">
        <p className="text-sm text-muted">비트코인 · {market}</p>
        <p className="text-4xl font-bold tracking-tight tabular-nums">{formatWon(last.close)}</p>
        <p className={`text-sm font-medium tabular-nums ${tone(change)}`}>
          {formatSignedWon(change)} ({formatPercent(change / prev.close)})
          <span className="ml-1 font-normal text-muted">전일 대비</span>
        </p>
        <p className="pt-1 text-xs text-muted">{formatDate(last.day)} 종가 기준</p>
      </section>

      <section className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex gap-1 rounded-xl bg-subtle p-1" role="tablist" aria-label="막대 단위">
            {INTERVALS.map((o) => (
              <button
                key={o.value}
                type="button"
                role="tab"
                aria-selected={o.value === interval}
                onClick={() => setInterval(o.value)}
                className={`w-12 rounded-lg py-1.5 text-sm font-medium transition-colors ${
                  o.value === interval ? "bg-background text-foreground shadow-sm" : "text-muted hover:text-foreground"
                }`}
              >
                {o.label}
              </button>
            ))}
          </div>
          {runs.length > 0 && (
            <label className="flex items-center gap-2 text-sm text-muted">
              매매 표시
              <select
                value={runId ?? ""}
                onChange={(e) => selectRun(e.target.value ? Number(e.target.value) : null)}
                className="rounded-lg bg-subtle px-2 py-1.5 text-sm text-foreground"
              >
                <option value="">표시 안 함</option>
                {[...runs].sort(byRuleOrder).map((r) => (
                  <option key={r.id} value={r.id}>
                    {`${ruleName(r.strategy)} 백테스트`}
                  </option>
                ))}
              </select>
            </label>
          )}
        </div>

        {run && (
          <p className="text-xs text-muted">
            {tradesState === "loading"
              ? "매매 기록을 불러오는 중"
              : tradesState === "error"
                ? "매매 기록을 불러오지 못했어요"
                : `${ruleName(run.strategy)} 백테스트 ${formatDate(run.start.slice(0, 10))} ~ ${formatDate(run.end.slice(0, 10))} · 매매 ${run.trades.toLocaleString("ko-KR")}건 · 코드 ${run.code_version} · 실제 거래가 아니에요`}
          </p>
        )}

        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 text-xs tabular-nums">
          <span className="font-medium">{barLabel(legend.day, interval)}</span>
          <span className="text-muted">
            시 <span className="text-foreground">{formatWon(legend.open)}</span>
          </span>
          <span className="text-muted">
            고 <span className="text-up">{formatWon(legend.high)}</span>
          </span>
          <span className="text-muted">
            저 <span className="text-down">{formatWon(legend.low)}</span>
          </span>
          <span className="text-muted">
            종 <span className={tone(legendChange)}>{formatWon(legend.close)}</span>
          </span>
        </div>

        {legendTrades && (
          <ul className="space-y-0.5 text-xs">
            {[...legendTrades.buys, ...legendTrades.sells].map((t, i) => (
              <li key={i} className="text-muted">
                <span className={t.side === "buy" ? "text-up" : "text-down"}>
                  {t.side === "buy" ? "매수" : "매도"} {formatWon(t.price)}
                </span>{" "}
                · {t.reason}
              </li>
            ))}
          </ul>
        )}

        <CandleChart
          candles={candles}
          markers={markers}
          initialBars={option.initialBars}
          onVisibleChange={(from, to) => setVisible({ interval, from, to })}
          onHover={(index) => setHover(index === null ? null : { interval, index })}
        />
      </section>

      {stats && (
        <section className="space-y-2">
          <p className="text-xs text-muted">
            보이는 구간 {formatDate(stats.from)} ~ {formatDate(stats.to)}
          </p>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
            <Stat label="구간 수익률" value={formatPercent(stats.ratio)} className={tone(stats.ratio)} />
            <Stat label="최고가" value={formatWon(stats.high)} />
            <Stat label="최저가" value={formatWon(stats.low)} />
          </div>
        </section>
      )}

      <p className="text-xs leading-relaxed text-muted">
        업비트 원화 시세 {formatDate(daily[0].day)}부터 {formatDate(last.day)}까지. 하루가 끝나 확정된 봉만
        보여주고, 아직 진행 중인 오늘 봉은 빼요. 주봉·월봉은 업비트와 같은 기준(월요일·1일 시작)으로 일봉을 묶어요.
      </p>
    </div>
  );
}

function Stat({ label, value, className = "" }: { label: string; value: string; className?: string }) {
  return (
    <div className="flex min-w-0 items-baseline justify-between rounded-xl bg-subtle px-4 py-3 sm:block">
      <p className="text-sm text-muted sm:text-xs">{label}</p>
      <p className={`font-semibold tabular-nums sm:mt-1 sm:truncate sm:text-sm ${className}`}>{value}</p>
    </div>
  );
}
