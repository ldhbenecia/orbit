import type { components } from "@/lib/api";
import { formatDate, formatPercent1 } from "@/lib/format";
import type { MarketInfo } from "@/lib/markets";
import { ruleShortName } from "@/lib/rules";
import { tone } from "@/lib/summary";

type Checks = components["schemas"]["RuleChecksOut"];
type Row = components["schemas"]["RuleCheckOut"];
type Period = Row["period"];

const SIGNAL_RULES = ["hold", "ma-60", "ma-120", "ma-200", "vb-0.5"];

// 결과가 특정 기간·특정 값 덕분인지 보는 곳 — 기간을 반으로 나눈 성과와 주변 파라미터
export function RuleCheckCard({ info, data }: { info: MarketInfo; data: Checks }) {
  const get = (strategy: string, period: Period) =>
    data.rows.find((r) => r.strategy === strategy && r.period === period);
  const hold = { first: get("hold", "first"), second: get("hold", "second"), all: get("hold", "all") };
  if (!hold.first || !hold.second || !hold.all) return null;
  const holdFirst = Number(hold.first.cagr);
  const holdSecond = Number(hold.second.cagr);

  const family = (prefix: string) =>
    data.rows
      .filter((r) => r.strategy.startsWith(prefix) && r.period === "all")
      .map((r) => r.strategy)
      .sort((a, b) => Number(a.split("-")[1]) - Number(b.split("-")[1]));
  const ma = family("ma-");
  const vb = family("vb-");

  return (
    <section className="space-y-5 rounded-2xl bg-subtle p-5">
      <div className="space-y-1">
        <p className="text-sm text-muted">규칙 검증 · {info.name}</p>
        <p className="text-lg font-bold">{verdict(ma, "이동평균 규칙", get, holdFirst, holdSecond)}</p>
        {vb.length > 0 && <p className="font-semibold">{verdict(vb, "변동성 돌파 규칙", get, holdFirst, holdSecond)}</p>}
        <p className="text-sm text-muted">{drawdowns(ma, get, Number(hold.all.mdd))}</p>
        <p className="text-xs text-muted">
          {formatDate(hold.all.start.slice(0, 10))} ~ {formatDate(hold.all.end.slice(0, 10))}을 반으로 나눠 봤어요 · 앞 절반
          ~{formatDate(hold.first.end.slice(0, 10))}
        </p>
      </div>

      <table className="w-full text-sm tabular-nums">
        <thead>
          <tr className="text-xs text-muted">
            <th className="py-1 text-left font-normal">연평균 수익 (CAGR)</th>
            <th className="py-1 text-right font-normal">앞 절반</th>
            <th className="py-1 text-right font-normal">뒤 절반</th>
            <th className="hidden py-1 text-right font-normal sm:table-cell">최대 하락</th>
            <th className="hidden py-1 text-right font-normal sm:table-cell">거래</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {SIGNAL_RULES.map((spec) => {
            const [first, second, all] = [get(spec, "first"), get(spec, "second"), get(spec, "all")];
            if (!first || !second || !all) return null;
            return (
              <tr key={spec}>
                <td className="py-2">{spec === "hold" ? "단순 보유 (비교 기준)" : ruleShortName(spec, info.group)}</td>
                <td className={`py-2 text-right ${tone(Number(first.cagr))}`}>{formatPercent1(Number(first.cagr))}</td>
                <td className={`py-2 text-right ${tone(Number(second.cagr))}`}>{formatPercent1(Number(second.cagr))}</td>
                <td className="hidden py-2 text-right text-muted sm:table-cell">{formatPercent1(Number(all.mdd))}</td>
                <td className="hidden py-2 text-right text-muted sm:table-cell">{all.trades.toLocaleString("ko-KR")}번</td>
              </tr>
            );
          })}
        </tbody>
      </table>

      <Sensitivity
        title={`이동평균 기간을 바꿔 보면 (${info.group === "stock" ? "거래일" : "일"})`}
        specs={ma}
        label={(spec) => spec.split("-")[1]}
        get={get}
        holdFirst={holdFirst}
        holdSecond={holdSecond}
      />
      {vb.length > 0 && (
        <Sensitivity
          title="변동성 돌파 k 를 바꿔 보면"
          specs={vb}
          label={(spec) => spec.split("-")[1]}
          get={get}
          holdFirst={holdFirst}
          holdSecond={holdSecond}
        />
      )}

      <OutOfSample specs={[...ma, ...vb]} get={get} holdSecond={holdSecond} group={info.group} />

      <p className="text-xs leading-relaxed text-muted">
        과거 데이터에서 이랬다는 것이지 앞으로도 같다는 뜻이 아니에요. 수수료·슬리피지·호가 단위를 넣고, 모든 규칙을 240번째 봉부터
        같은 출발선에서 비교했어요. {formatDate(data.created_at.slice(0, 10))} 검증 · 코드 {data.code_version}
      </p>
    </section>
  );
}

type Get = (strategy: string, period: Period) => Row | undefined;

function verdict(specs: string[], name: string, get: Get, holdFirst: number, holdSecond: number) {
  const both = specs.filter(
    (s) => Number(get(s, "first")?.cagr) > holdFirst && Number(get(s, "second")?.cagr) > holdSecond,
  ).length;
  if (both === specs.length) return `${name}은 어떤 값이든 두 기간 모두 단순 보유보다 나았어요`;
  if (both === 0) {
    const firstOnly = specs.filter((s) => Number(get(s, "first")?.cagr) > holdFirst).length;
    const secondOnly = specs.filter((s) => Number(get(s, "second")?.cagr) > holdSecond).length;
    if (firstOnly > 0 && secondOnly === 0) return `${name}은 앞 절반에서만 나았고 뒤 절반에선 단순 보유보다 못했어요`;
    if (secondOnly > 0 && firstOnly === 0) return `${name}은 뒤 절반에서만 나았고 앞 절반에선 단순 보유보다 못했어요`;
    if (firstOnly > 0) return `${name}은 한쪽 기간에서만 나았고, 두 기간 모두 단순 보유보다 나은 값은 없었어요`;
    return `${name}은 두 기간 모두 단순 보유보다 못했어요`;
  }
  return `${name}은 ${specs.length}개 값 중 ${both}개만 두 기간 모두 단순 보유보다 나았어요`;
}

// 수익만 보면 반쪽 — 같은 기간 가장 크게 잃었던 폭도 함께
function drawdowns(specs: string[], get: Get, holdMdd: number) {
  const values = specs.map((s) => Number(get(s, "all")?.mdd ?? 0));
  const [best, worst] = [Math.max(...values), Math.min(...values)];
  return `최대 하락은 단순 보유 ${formatPercent1(holdMdd)}, 이동평균 규칙 ${formatPercent1(best)} ~ ${formatPercent1(worst)}`;
}

// 막대 두 개(앞·뒤 절반)와 단순 보유 기준선 — 주변 값도 비슷해야 우연이 아님
function Sensitivity({
  title,
  specs,
  label,
  get,
  holdFirst,
  holdSecond,
}: {
  title: string;
  specs: string[];
  label: (spec: string) => string;
  get: Get;
  holdFirst: number;
  holdSecond: number;
}) {
  const values = specs.flatMap((s) => [Number(get(s, "first")?.cagr ?? 0), Number(get(s, "second")?.cagr ?? 0)]);
  const top = Math.max(0, holdFirst, holdSecond, ...values);
  const bottom = Math.min(0, holdFirst, holdSecond, ...values);
  const span = top - bottom || 1;
  const H = 120;
  const y = (v: number) => ((top - v) / span) * H;
  const slot = 100 / specs.length;

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-sm font-medium">{title}</p>
        <p className="flex items-center gap-3 text-[11px] text-muted">
          <span className="flex items-center gap-1">
            <span className="inline-block size-2 rounded-sm bg-muted/40" />앞 절반
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block size-2 rounded-sm bg-foreground/70" />뒤 절반
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block h-px w-3 border-t border-dashed border-foreground" />단순 보유
          </span>
        </p>
      </div>
      <svg viewBox={`0 0 100 ${H}`} preserveAspectRatio="none" className="h-32 w-full" aria-label={title}>
        <line x1="0" x2="100" y1={y(0)} y2={y(0)} stroke="var(--border)" strokeWidth="1" vectorEffect="non-scaling-stroke" />
        {specs.map((s, i) => {
          const f = Number(get(s, "first")?.cagr ?? 0);
          const b = Number(get(s, "second")?.cagr ?? 0);
          const x = i * slot + slot * 0.15;
          const w = slot * 0.33;
          const bar = (v: number, dx: number, cls: string) => (
            <rect x={x + dx} width={w} y={Math.min(y(v), y(0))} height={Math.abs(y(v) - y(0))} className={cls}>
              <title>{`${label(s)}: ${formatPercent1(v)}`}</title>
            </rect>
          );
          return (
            <g key={s}>
              {bar(f, 0, "fill-muted/40")}
              {bar(b, w + slot * 0.04, "fill-foreground/70")}
            </g>
          );
        })}
        {[holdFirst, holdSecond].map((v, i) => (
          <line
            key={i}
            x1="0"
            x2="100"
            y1={y(v)}
            y2={y(v)}
            stroke="var(--foreground)"
            strokeOpacity={i === 0 ? 0.35 : 0.8}
            strokeDasharray="4 3"
            strokeWidth="1"
            vectorEffect="non-scaling-stroke"
          />
        ))}
      </svg>
      <div className="grid text-center text-[11px] text-muted tabular-nums" style={{ gridTemplateColumns: `repeat(${specs.length}, minmax(0, 1fr))` }}>
        {specs.map((s) => (
          <span key={s}>{label(s)}</span>
        ))}
      </div>
    </div>
  );
}

// 과최적화 점검 — 앞 절반만 보고 고른 값이 뒤 절반에서도 통했는지
function OutOfSample({ specs, get, holdSecond, group }: { specs: string[]; get: Get; holdSecond: number; group: MarketInfo["group"] }) {
  const best = specs.reduce<string | null>(
    (acc, s) => (acc === null || Number(get(s, "first")?.cagr) > Number(get(acc, "first")?.cagr) ? s : acc),
    null,
  );
  if (!best) return null;
  const first = Number(get(best, "first")?.cagr);
  const second = Number(get(best, "second")?.cagr);
  const beat = second > holdSecond;
  return (
    <div className="rounded-xl bg-background px-4 py-3 text-sm">
      <p>
        앞 절반에서 가장 좋았던 <span className="font-semibold">{ruleShortName(best, group)}</span>
        {best.startsWith("vb") && ` (k ${best.split("-")[1]})`}
        <span className={`ml-1 tabular-nums ${tone(first)}`}>{formatPercent1(first)}</span>
      </p>
      <p className="mt-1 text-muted">
        → 뒤 절반에서는 <span className={`tabular-nums ${tone(second)}`}>{formatPercent1(second)}</span>, 단순 보유{" "}
        <span className="tabular-nums">{formatPercent1(holdSecond)}</span>
        {beat ? "보다 나았어요" : "보다 못했어요"}
      </p>
      <p className="mt-1 text-xs text-muted">
        과거에 제일 좋았던 값을 고르는 건 쉬워요. 고른 뒤의 기간에서도 통하는지가 진짜 검증이에요.
      </p>
    </div>
  );
}
