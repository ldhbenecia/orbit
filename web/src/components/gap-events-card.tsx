import { RuleStory } from "@/components/rule-story";
import type { components } from "@/lib/api";
import { formatDate, formatPercent1 } from "@/lib/format";
import type { MarketInfo } from "@/lib/markets";
import { tone } from "@/lib/summary";

type Events = components["schemas"]["GapEventsOut"];
type GapEvent = components["schemas"]["GapEventOut"];

// 지나간 사실의 기록 — 사라는 신호가 아님. "그 뒤 1개월" 은 지나고 나서야 아는 값
export function GapEventsCard({ info, data }: { info: MarketInfo; data: Events }) {
  return (
    <section className="space-y-4 rounded-2xl bg-subtle p-5">
      <div className="space-y-1">
        <p className="text-sm text-muted">큰 갭 상승 기록 · {info.name}</p>
        <p className="text-xl font-bold">
          {data.total > 0 ? `전체 기간 ${data.total}번` : "조건에 맞는 날이 없었어요"}
        </p>
        <p className="text-xs text-muted">시가가 전날 종가보다 10% 이상 높게 시작하고 거래량이 평소의 3배 이상인 날</p>
      </div>

      {data.events.length > 0 && (
        <ul className="divide-y divide-border">
          {data.events.map((e) => (
            <EventRow key={e.day} event={e} />
          ))}
        </ul>
      )}

      <RuleStory story="gap" />

      <p className="text-xs leading-relaxed text-muted">
        &quot;그 뒤 1개월&quot; 은 지나고 나서야 아는 값이라, 그날 알 수 있던 건 갭·거래량·직전 6개월뿐이에요. 분기 보고서
        공시일은 SEC 기준이라 실제 실적 발표(보도자료)는 그보다 며칠~몇 주 앞서요. 분석용이고 투자 권유가 아니에요.
      </p>
    </section>
  );
}

function EventRow({ event: e }: { event: GapEvent }) {
  const pct = (v: string) => formatPercent1(Number(v));
  return (
    <li className="space-y-1 py-3 text-sm">
      <div className="flex items-baseline justify-between gap-3">
        <span className="font-medium">{formatDate(e.day)}</span>
        <span className="shrink-0 tabular-nums">
          갭 <span className={tone(Number(e.gap))}>{pct(e.gap)}</span>
          <span className="ml-2 text-xs text-muted">거래량 {Number(e.volume_multiple).toFixed(1)}배</span>
        </span>
      </div>
      <p className="text-xs tabular-nums text-muted">
        그날 종가 <span className={tone(Number(e.day_return))}>{pct(e.day_return)}</span>
        {e.prior !== null && (
          <>
            {" · "}직전 6개월 <span className={tone(Number(e.prior))}>{pct(e.prior)}</span>
          </>
        )}
        {" · "}그 뒤 1개월{" "}
        {e.after === null ? "아직" : <span className={tone(Number(e.after))}>{pct(e.after)}</span>}
      </p>
      {e.filed_near && <p className="text-xs text-muted">분기 보고서 공시 {formatDate(e.filed_near)} 무렵</p>}
    </li>
  );
}
