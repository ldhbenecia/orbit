import { RuleStory } from "@/components/rule-story";
import type { components } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { MarketInfo } from "@/lib/markets";

type Template = components["schemas"]["TrendTemplateOut"];
type Check = components["schemas"]["TemplateCheckOut"]["check"];

// 조건마다 쉬운 말 — 조건이 늘면 여기서 타입 검사가 깨짐
export const CHECK_LABEL: Record<Check, string> = {
  above_150_200: "주가가 150일·200일 평균 위",
  ma150_over_200: "150일 평균이 200일 평균 위",
  ma200_rising: "200일 평균이 한 달 전보다 높음",
  ma50_over_long: "50일 평균이 150일·200일 평균 위",
  above_50: "주가가 50일 평균 위",
  above_low: "1년 최저가보다 30% 이상 위",
  near_high: "1년 최고가에서 25% 이내",
  strong: "1년 수익률이 등록한 종목 중 상위 30%",
};

// 사라·말라가 아니라 "지금 상승 추세 조건을 몇 개 갖췄나" — 손익이 아니라 색을 쓰지 않음
export function TrendTemplateCard({ info, data }: { info: MarketInfo; data: Template }) {
  return (
    <section className="space-y-4 rounded-2xl bg-subtle p-5">
      <div className="space-y-1">
        <p className="text-sm text-muted">추세 템플릿 · {info.name}</p>
        <p className="text-xl font-bold tabular-nums">
          {data.known}개 조건 중 {data.passed}개 충족
        </p>
        <p className="text-xs text-muted">{formatDate(data.as_of.slice(0, 10))} 확정 봉 기준</p>
      </div>

      <ul className="space-y-1.5 text-sm">
        {data.checks.map((c) => (
          <li key={c.check} className="flex items-baseline justify-between gap-3">
            <span className={c.passed ? "" : "text-muted"}>{CHECK_LABEL[c.check]}</span>
            <span className="shrink-0 text-xs text-muted">
              {c.passed === null ? "모름" : c.passed ? "충족" : "아님"}
            </span>
          </li>
        ))}
      </ul>

      <RuleStory story="template" />

      <p className="text-xs leading-relaxed text-muted">
        상대강도는 등록한 주식 {data.peers}개끼리 1년 수익률을 비교했어요
        {data.peers < 5 ? " — 5개보다 적어 판단하지 않았어요" : ""}. 조건을 많이 갖춘 건 이미 오른 종목이라는 뜻이지
        사라는 뜻이 아니에요.
      </p>
    </section>
  );
}
