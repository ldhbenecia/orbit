import type { components } from "@/lib/api";

type Signals = components["schemas"]["SignalsOut"];
type Dca = components["schemas"]["DcaOut"];
type Stance = components["schemas"]["Stance"];

export const STANCE: Record<Stance, { label: string; tone: string; buySide: boolean }> = {
  hold: { label: "보유 구간", tone: "text-up", buySide: true },
  cash: { label: "현금 구간", tone: "text-down", buySide: false },
  breakout_hit: { label: "오늘 돌파함", tone: "text-up", buySide: true },
  breakout_wait: { label: "돌파 대기", tone: "text-muted", buySide: false },
};

export const buySideCount = (data: Signals) => data.signals.filter((s) => STANCE[s.stance].buySide).length;

// 기호(+/−) 대신 말로 — 적립하는 입장에서는 평균보다 싸게 사는지가 관심사
export const NEAR = 0.005; // 0.5% 안쪽은 평균과 같다고 봄 — 색으로 강조하지 않음
export const position = (gap: number) => {
  if (Math.abs(gap) < NEAR) return "평균과 거의 같음";
  return `평균보다 ${Math.abs(gap * 100).toFixed(1)}% ${gap > 0 ? "비쌈" : "쌈"}`;
};

export const tone = (value: number) => (value > 0 ? "text-up" : value < 0 ? "text-down" : "text-muted");

export type Line = { text: string; tone: string };

// 전 종목 목록의 한 줄 — 모두 매수 쪽·모두 아님일 때만 색, 섞이면 중립
export const signalLine = (data: Signals): Line => {
  const buySide = buySideCount(data);
  const total = data.signals.length;
  return {
    text: `규칙 ${total}개 중 ${buySide}개 매수 쪽`,
    tone: buySide === total ? "text-up" : buySide === 0 ? "text-down" : "text-foreground",
  };
};

// 코어 ETF 는 사라·말라가 아니라 다음 적립일과 지금 가격 위치
export const dcaLine = (data: Dca): Line => {
  const when = data.days_until === 0 ? "오늘 적립" : `적립 D-${data.days_until}`;
  const first = data.positions[0];
  if (!first) return { text: when, tone: "text-muted" };
  const gap = Number(first.gap);
  return {
    text: `${when} · ${Math.round(first.window / 21)}개월 ${position(gap)}`,
    tone: Math.abs(gap) < NEAR ? "text-muted" : tone(gap),
  };
};
