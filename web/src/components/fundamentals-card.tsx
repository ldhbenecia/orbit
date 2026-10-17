import type { components } from "@/lib/api";
import { formatDate, formatMultiple, formatPercent1, formatRatio } from "@/lib/format";
import type { MarketInfo } from "@/lib/markets";

type Fundamentals = components["schemas"]["FundamentalsOut"];
type Position = components["schemas"]["PositionOut"];


// 지난 5년 월말 값 중 지금 위치 — 낮은 쪽이면 "하위", 높은 쪽이면 "상위" 로 (하위 97% 처럼 헷갈리지 않게)
export const rankLabel = (p: Position) => {
  const share = Number(p.percentile);
  if (share >= 1) return "최고";
  if (share <= 0) return "최저";
  return share < 0.5
    ? `하위 ${Math.max(1, Math.round(share * 100))}%`
    : `상위 ${Math.max(1, Math.round((1 - share) * 100))}%`;
};
const positionLabel = (p: Position) => `5년 중 ${rankLabel(p)}`;

// 싸다·비싸다 판단 없이 숫자와 과거 대비 위치만 — 손익이 아니라서 색을 쓰지 않음
export function FundamentalsCard({ info, data }: { info: MarketInfo; data: Fundamentals }) {
  return (
    <section className="space-y-5 rounded-2xl bg-subtle p-5">
      <div className="space-y-1">
        <p className="text-sm text-muted">재무 · {info.name}</p>
        <p className="text-xl font-bold tabular-nums">
          {data.per !== null
            ? `PER ${formatMultiple(data.per)}`
            : data.loss
              ? "PER 없음 (최근 4분기 적자)"
              : "PER 없음 (주식 수·재무 부족)"}
        </p>
        {data.per_5y && <Range position={data.per_5y} />}
      </div>

      <div className="grid grid-cols-2 gap-2">
        <Stat
          label="PBR"
          value={formatMultiple(data.pbr)}
          sub={data.pbr_5y ? positionLabel(data.pbr_5y) : undefined}
          hint="시가총액 ÷ 자본총계 — 회사가 가진 순자산의 몇 배로 거래되는지"
        />
        <Stat label="ROE" value={formatRatio(data.roe)} hint="최근 4분기 순이익 ÷ 자본총계 — 자본으로 얼마나 벌었는지" />
        <Stat
          label="FCF 수익률"
          value={formatRatio(data.fcf_yield)}
          hint="(영업현금흐름 − 설비투자) ÷ 시가총액 — 지금 가격에 사면 1년 동안 남는 현금 비율"
        />
        <Stat
          label="매출 성장 (1년)"
          value={data.revenue_growth === null ? "—" : formatPercent1(Number(data.revenue_growth))}
          hint="최근 4분기 매출 ÷ 1년 전 최근 4분기 매출 − 1"
        />
      </div>

      <p className="text-xs leading-relaxed text-muted">
        {formatDate(data.period_end)}까지 최근 4분기 · {formatDate(data.filed)} 공시 (SEC) · {formatDate(data.as_of)} 종가
        기준. PER 이 낮다고 싼 건 아니에요 — 시장이 이익이 줄 거라고 보는 걸 수도 있어요. 분석용이고 투자 권유가
        아니에요.
      </p>
    </section>
  );
}

function Range({ position }: { position: Position }) {
  const pct = Number(position.percentile) * 100;
  return (
    <div className="space-y-1.5 pt-2">
      <p className="text-sm">
        {positionLabel(position)}
        <span className="ml-1.5 text-xs text-muted">
          (월말 {position.months}개 · {formatMultiple(position.low)}~{formatMultiple(position.high)})
        </span>
      </p>
      <div className="relative h-1.5 rounded-full bg-background" aria-hidden>
        <span
          className="absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full bg-foreground"
          style={{ left: `${pct}%` }}
        />
      </div>
      <div className="flex justify-between text-[11px] text-muted" aria-hidden>
        <span>5년 중 낮음</span>
        <span>높음</span>
      </div>
    </div>
  );
}

function Stat({ label, value, sub, hint }: { label: string; value: string; sub?: string; hint: string }) {
  return (
    <div className="min-w-0 rounded-xl bg-background px-4 py-3" title={hint}>
      <p className="text-xs text-muted">{label}</p>
      <p className="mt-1 text-sm font-semibold tabular-nums">{value}</p>
      {sub && <p className="text-[11px] text-muted">{sub}</p>}
    </div>
  );
}
