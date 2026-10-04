"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { CandleChart, type ChartMarker } from "@/components/candle-chart";
import { SegmentedControl } from "@/components/segmented-control";
import type { components } from "@/lib/api";
import { type CandleOut, type ChartCandle, type Interval, toChartCandle } from "@/lib/candles";
import { formatDate, formatPercent, formatPrice, formatSignedPrice } from "@/lib/format";
import type { MarketInfo } from "@/lib/markets";
import { ruleName } from "@/lib/rules";
import { type ChartTrade, groupByBar, toChartTrade } from "@/lib/trades";

type Run = components["schemas"]["RunOut"];
type TradesState = ChartTrade[] | "loading" | "error";
type Series = { candles: ChartCandle[]; complete: boolean }; // complete — 처음부터 끝까지 다 받았는지

const LOAD_OLDER_MARGIN = 20; // 보이는 구간이 받은 일봉 왼쪽 끝에서 이만큼 안으로 오면 나머지를 받음

async function fetchCandles(market: string, interval: Interval): Promise<ChartCandle[]> {
  const res = await fetch(`/api/candles?market=${market}&interval=${interval}`);
  if (!res.ok) throw new Error(String(res.status));
  return ((await res.json()) as CandleOut[]).map(toChartCandle);
}

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
  info: MarketInfo;
  runs: Run[];
  recentDaily: ChartCandle[]; // 처음 화면용 최근 일봉
  dailyCount: number; // 전체 일봉 개수
  firstDay: string; // 전체 데이터 첫날
};

export function PriceView({ info, runs, recentDaily, dailyCount, firstDay }: Props) {
  const price = (value: number) => formatPrice(value, info.currency);
  const [series, setSeries] = useState<Partial<Record<Interval, Series>>>({
    day: { candles: recentDaily, complete: recentDaily.length >= dailyCount },
  });
  // 탭은 누르자마자 바뀌고(requested) 차트는 데이터가 오면 바뀜(interval)
  const [interval, setInterval] = useState<Interval>("day");
  const [requested, setRequested] = useState<Interval>("day");
  const latestRequest = useRef<Interval>("day");
  const [loadError, setLoadError] = useState(false);
  const loadingOlder = useRef(false);
  const [runId, setRunId] = useState<number | null>(null);
  const [tradesByRun, setTradesByRun] = useState<Record<number, TradesState>>({});
  // 막대 위치는 단위마다 다름 — 어느 단위의 위치인지 같이 저장해 단위를 바꾼 직후 옛 위치를 쓰지 않음
  const [visibleState, setVisible] = useState<{ interval: Interval; from: number; to: number } | null>(null);
  const [hoverState, setHover] = useState<{ interval: Interval; length: number; index: number } | null>(null);

  const daily = series.day!.candles;
  const candles = series[interval]!.candles;
  const option = INTERVALS.find((o) => o.value === interval)!;
  const visible = visibleState?.interval === interval ? visibleState : null;
  // 과거 일봉을 앞에 붙이면 인덱스가 밀림 — 길이까지 같을 때만 호버 위치를 믿음
  const hover =
    hoverState?.interval === interval && hoverState.length === candles.length ? hoverState.index : null;

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
  const legendTradeText = legendTrades
    ? [...legendTrades.buys, ...legendTrades.sells]
        .map((t) => `${t.side === "buy" ? "매수" : "매도"} ${price(t.price)} · ${t.reason}`)
        .join(" / ")
    : null;


  const selectInterval = async (next: Interval) => {
    setRequested(next);
    latestRequest.current = next;
    setLoadError(false);
    if (series[next]) {
      setInterval(next);
      return;
    }
    try {
      const loaded = await fetchCandles(info.market, next);
      setSeries((prev) => ({ ...prev, [next]: { candles: loaded, complete: true } }));
      // 빠르게 연달아 누르면 마지막으로 누른 단위만 화면에 반영
      if (latestRequest.current === next) setInterval(next);
    } catch {
      if (latestRequest.current === next) {
        setRequested(interval);
        setLoadError(true);
      }
    }
  };

  // 과거로 밀어 받은 일봉의 왼쪽 끝에 가까워지면 나머지 일봉을 받아 앞에 붙임
  useEffect(() => {
    if (interval !== "day" || !visible || series.day!.complete || loadingOlder.current) return;
    if (visible.from > LOAD_OLDER_MARGIN) return;
    loadingOlder.current = true;
    fetchCandles(info.market, "day")
      .then((all) => setSeries((prev) => ({ ...prev, day: { candles: all, complete: true } })))
      .catch(() => setLoadError(true))
      .finally(() => {
        loadingOlder.current = false;
      });
  }, [interval, visible, series.day, info.market]);

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
        <p className="text-sm text-muted">
          {info.name} · {info.market}
        </p>
        <p className="text-4xl font-bold tracking-tight tabular-nums">{price(last.close)}</p>
        <p className={`text-sm font-medium tabular-nums ${tone(change)}`}>
          {formatSignedPrice(change, info.currency)} ({formatPercent(change / prev.close)})
          <span className="ml-1 font-normal text-muted">전일 대비</span>
        </p>
        <p className="pt-1 text-xs text-muted">{formatDate(last.day)} 종가 기준</p>
      </section>

      <section className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <SegmentedControl
            label="막대 단위"
            options={INTERVALS}
            value={requested}
            onChange={selectInterval}
            className="w-40"
          />
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

        {/* 범례 줄은 높이를 고정 — 값에 따라 줄 수가 바뀌면 차트가 위아래로 밀림 */}
        <div className="flex min-h-10 flex-wrap content-start items-baseline gap-x-3 gap-y-1 text-xs tabular-nums sm:min-h-5">
          <span className="font-medium">{barLabel(legend.day, interval)}</span>
          <span className="text-muted">
            시 <span className="text-foreground">{price(legend.open)}</span>
          </span>
          <span className="text-muted">
            고 <span className="text-up">{price(legend.high)}</span>
          </span>
          <span className="text-muted">
            저 <span className="text-down">{price(legend.low)}</span>
          </span>
          <span className="text-muted">
            종 <span className={tone(legendChange)}>{price(legend.close)}</span>
          </span>
        </div>

        {run && (
          <p
            className={`h-5 truncate text-xs ${legendTradeText ? "text-foreground" : "text-muted"}`}
            title={legendTradeText ?? undefined}
          >
            {legendTradeText ?? "막대에 올리면 그날 매매와 이유가 보여요"}
          </p>
        )}

        {loadError && <p className="text-xs text-down">차트 데이터를 불러오지 못했어요. 다시 눌러 주세요.</p>}

        <div className={`transition-opacity duration-200 ${requested !== interval ? "opacity-50" : ""}`}>
          <CandleChart
            currency={info.currency}
            resetKey={interval}
            candles={candles}
            markers={markers}
            initialBars={option.initialBars}
            onVisibleChange={(from, to) => setVisible({ interval, from, to })}
            onHover={(index) => setHover(index === null ? null : { interval, length: candles.length, index })}
          />
        </div>
      </section>

      {stats && (
        <section className="space-y-2">
          <p className="text-xs text-muted">
            보이는 구간 {formatDate(stats.from)} ~ {formatDate(stats.to)}
          </p>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
            <Stat label="구간 수익률" value={formatPercent(stats.ratio)} className={tone(stats.ratio)} />
            <Stat label="최고가" value={price(stats.high)} />
            <Stat label="최저가" value={price(stats.low)} />
          </div>
        </section>
      )}

      <p className="text-xs leading-relaxed text-muted">
        {info.source} 시세 {formatDate(firstDay)}부터 {formatDate(last.day)}까지 {dailyCount.toLocaleString("ko-KR")}일. 거래일이 끝나 확정된 봉만
        보여주고, 아직 진행 중인 봉은 빼요. 주봉·월봉은 월요일·1일 시작 기준으로 일봉을 묶어요.
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
