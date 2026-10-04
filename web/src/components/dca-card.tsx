import type { components } from "@/lib/api";
import { formatDate, formatKoreanWon, formatPercent1, formatWon } from "@/lib/format";
import type { MarketInfo } from "@/lib/markets";
import { NEAR, position, tone } from "@/lib/summary";

type Dca = components["schemas"]["DcaOut"];

const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"];

const withWeekday = (day: string) => `${formatDate(day)} (${WEEKDAYS[new Date(`${day}T00:00:00Z`).getUTCDay()]})`;

// 코어 ETF 는 다른 계좌에서 매달 25일(휴일이면 직전 영업일) 적립 — 보유/현금이 아니라 적립 관점으로 보여줌
export function DcaCard({ info, data }: { info: MarketInfo; data: Dca }) {
  const invested = Number(data.invested);
  const finalValue = Number(data.final_value);
  const ret = Number(data.return_on_invested);
  const worst = Number(data.worst_vs_invested);

  return (
    <section className="space-y-5 rounded-2xl bg-subtle p-5">
      <div className="space-y-1">
        <p className="text-sm text-muted">적립식 분석 · {info.name}</p>
        <p className="text-xl font-bold">
          다음 적립일 {withWeekday(data.next_payday)}
          <span className="ml-2 text-base font-medium text-muted">
            {data.days_until === 0 ? "오늘" : `D-${data.days_until}`}
          </span>
        </p>
        <p className="text-xs text-muted">
          매달 25일, 휴일이면 그 전 영업일
          {data.holidays_checked ? " · 장 캘린더로 공휴일 확인함" : " · 공휴일 미확인 (주말만 피함)"}
        </p>
      </div>

      <div className="space-y-2">
        <p className="text-sm font-medium">지금 가격 위치</p>
        <p className="text-xs text-muted">
          {formatDate(data.as_of.slice(0, 10))} 종가 {formatWon(Number(data.close))} 기준
        </p>
        <ul className="divide-y divide-border">
          {data.positions.map((p) => (
            <li key={p.window} className="flex items-baseline justify-between gap-3 py-2 text-sm">
              <span className="text-muted">
                최근 {p.window}거래일 (약 {Math.round(p.window / 21)}개월) 평균 {formatWon(Number(p.average))}
              </span>
              <span
                className={`shrink-0 rounded-md bg-background px-2 py-0.5 text-xs font-medium tabular-nums ${Math.abs(Number(p.gap)) < NEAR ? "text-muted" : tone(Number(p.gap))}`}
              >
                {position(Number(p.gap))}
              </span>
            </li>
          ))}
        </ul>
      </div>

      {data.first_buy && (
        <div className="space-y-3">
          <p className="text-sm font-medium">
            {formatDate(data.first_buy.slice(0, 10))}부터 매달 {formatKoreanWon(Number(data.monthly))}씩 샀다면
            <span className="ml-1 font-normal text-muted">({data.months}개월)</span>
          </p>
          <div className="rounded-xl bg-background px-4 py-4">
            <p className="text-sm text-muted">{formatKoreanWon(invested)} 넣어서 지금</p>
            <p className="mt-1 flex flex-wrap items-baseline gap-x-2">
              <span className="text-2xl font-bold tabular-nums">{formatKoreanWon(finalValue)}</span>
              <span className={`text-base font-semibold tabular-nums ${tone(ret)}`}>{formatPercent1(ret)}</span>
            </p>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <Stat
              label="가장 나빴던 순간"
              value={worst < 0 ? formatPercent1(worst) : "손실 없음"}
              className={tone(worst)}
            />
            {data.average_cost && (
              <Stat
                label="평균 매수가 → 지금"
                value={`${formatWon(Number(data.average_cost))} → ${formatWon(Number(data.close))}`}
              />
            )}
          </div>
        </div>
      )}

      <p className="text-xs leading-relaxed text-muted">
        분석용이에요 — 투자 권유가 아니에요. 적립일 종가에 1주 단위로 샀다고 보고 남은 돈은 다음 달로 넘겼어요. 금액은
        예시이고, 매매 수수료는 빼고 계산했어요.
      </p>
    </section>
  );
}

function Stat({ label, value, className = "" }: { label: string; value: string; className?: string }) {
  return (
    <div className="min-w-0 rounded-xl bg-background px-4 py-3">
      <p className="text-xs text-muted">{label}</p>
      <p className={`mt-1 text-sm font-semibold tabular-nums ${className}`}>{value}</p>
    </div>
  );
}
