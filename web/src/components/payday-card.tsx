import type { components } from "@/lib/api";
import { formatDate, formatPercent1, formatUsdWhole } from "@/lib/format";
import { RuleStory } from "@/components/rule-story";
import type { MarketInfo } from "@/lib/markets";
import type { StoryKey } from "@/lib/rule-stories";
import { tone } from "@/lib/summary";

type Payday = components["schemas"]["PaydayOut"];
type Rule = components["schemas"]["PaydayRuleOut"]["rule"];

// 규칙마다 이름과 한 줄 설명 — 규칙이 늘면 여기서 타입 검사가 깨짐
const RULES: Record<Rule, { label: string; how: string; story: StoryKey }> = {
  plain: { label: "단순 적립", how: "매달 들어온 돈을 전부 삼", story: "dca" },
  dip: { label: "떨어지면 더", how: "평소엔 절반만, 52주 고점 대비 −20% 이하면 모아 둔 돈까지", story: "dip" },
  trend: { label: "추세 아래면 대기", how: "200거래일 평균 아래면 모아 두고, 위로 오면 전부", story: "ma" },
};

// 같은 돈을 같은 날 넣었을 때 규칙만 다르면 어땠는지 — 과거 결과, 앞으로가 아님
export function PaydayCard({ info, data }: { info: MarketInfo; data: Payday }) {
  const usd = (value: string) => formatUsdWhole(Number(value));
  const plain = data.rules.find((r) => r.rule === "plain");
  return (
    <section className="space-y-5 rounded-2xl bg-subtle p-5">
      <div className="space-y-1">
        <p className="text-sm text-muted">월급날 규칙 비교 · {info.name}</p>
        <p className="text-xl font-bold">
          {formatDate(data.start.slice(0, 10))}부터 매달 {usd(data.monthly)}씩 넣었다면
        </p>
        {plain && <p className="text-xs text-muted">모두 같은 날 같은 돈 {usd(plain.invested)} 을 넣음</p>}
      </div>

      <ul className="divide-y divide-border">
        {data.rules.map((r) => {
          const ret = Number(r.return_on_invested);
          return (
            <li key={r.rule} className="space-y-1 py-3">
              <div className="flex items-baseline justify-between gap-3">
                <span className="text-sm font-medium">{RULES[r.rule].label}</span>
                <span className="tabular-nums">
                  <span className="text-sm font-semibold">{usd(r.final_value)}</span>
                  <span className={`ml-2 text-xs ${tone(ret)}`}>{formatPercent1(ret)}</span>
                </span>
              </div>
              <p className="text-xs text-muted">{RULES[r.rule].how}</p>
              <p className="text-xs tabular-nums text-muted">
                가장 나빴던 순간 {formatPercent1(Number(r.worst_vs_invested))}
                {Number(r.cash) >= 1 && ` · 안 쓴 돈 ${usd(r.cash)}`}
                {r.beat_plain !== null &&
                  ` · 5년 구간 ${data.windows}개 중 ${Math.round(Number(r.beat_plain) * 100)}% 에서 단순 적립보다 많음`}
              </p>
              <RuleStory story={RULES[r.rule].story} />
            </li>
          );
        })}
      </ul>

      <div className="space-y-2">
        <p className="text-sm font-medium">다음 월급날엔</p>
        <ul className="space-y-1 text-xs">
          {data.rules.map((r) => (
            <li key={r.rule} className="flex gap-2">
              <span className="w-24 shrink-0 text-muted">{RULES[r.rule].label}</span>
              <span>{r.next_reason}</span>
            </li>
          ))}
        </ul>
        <p className="text-xs text-muted">{formatDate(data.as_of.slice(0, 10))} 종가 기준</p>
      </div>

      <p className="text-xs leading-relaxed text-muted">
        월급날(25일, 휴일이면 그 전 거래일) 종가에 1주 단위로, 수수료 0.1% 포함. 판단은 그 전날까지의 종가로만 했어요.
        안 쓴 돈에는 이자를 넣지 않았어요. 금액은 예시이고, 과거 데이터에서 이랬다는 것일 뿐 투자 권유가 아니에요.
      </p>
    </section>
  );
}
