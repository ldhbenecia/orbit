import type { MarketGroup } from "@/lib/markets";
import type { StoryKey } from "@/lib/rule-stories";

// 주식은 주말·휴장일이 빠져 N 개 봉이 N 거래일 (한 달 약 21거래일), 코인은 그냥 N 일
const months = (n: number, group: MarketGroup) => Math.round(n / (group === "stock" ? 21 : 30));

export const ruleName = (spec: string, group: MarketGroup) => {
  const [name, arg] = spec.split("-");
  if (name === "hold") return "단순 보유";
  if (name === "ma") {
    const n = Number(arg);
    return `최근 ${n}${group === "stock" ? "거래일" : "일"} 평균가 규칙 (약 ${months(n, group)}개월)`;
  }
  if (name === "vb") return `변동성 돌파 규칙 (k ${arg})`;
  if (name === "mom") return `${months(Number(arg), group)}개월 모멘텀 규칙`;
  return spec;
};

// 좁은 화면에서 한 줄에 들어가도록 이름은 짧게, 기간·파라미터는 따로
export const ruleShortName = (spec: string, group: MarketGroup) => {
  const [name, arg] = spec.split("-");
  if (name === "ma") return `최근 ${arg}${group === "stock" ? "거래일" : "일"} 평균가 규칙`;
  if (name === "vb") return "변동성 돌파 규칙";
  if (name === "mom") return `${months(Number(arg), group)}개월 모멘텀 규칙`;
  return ruleName(spec, group);
};

export const ruleParam = (spec: string, group: MarketGroup) => {
  const [name, arg] = spec.split("-");
  if (name === "ma") return `약 ${months(Number(arg), group)}개월`;
  if (name === "vb") return `k ${arg}`;
  if (name === "mom") return `${arg}${group === "stock" ? "거래일" : "일"} 전과 비교`;
  return null;
};

export const ruleDescription = (spec: string) => {
  const [name, arg] = spec.split("-");
  if (name === "ma") return "가격이 이 기간 평균보다 높으면 들고, 낮으면 팔고 쉬는 규칙";
  if (name === "vb") {
    const share = Number(arg) === 0.5 ? "절반" : `${Number(arg) * 100}%`;
    return `오늘 가격이 어제 오르내린 폭의 ${share}만큼 시가보다 오르면 사고, 다음 날 아침에 파는 규칙`;
  }
  if (name === "mom") return "지금 가격이 그때보다 높으면 들고, 아니면 팔고 쉬는 규칙";
  if (name === "hold") return "처음 사서 끝까지 들고 있는 비교 기준";
  return "";
};

// 규칙 계열마다 배경 설명 — 단순 보유는 비교 기준이라 없음
export const ruleStory = (spec: string): StoryKey | null => {
  const [name] = spec.split("-");
  if (name === "ma") return "ma";
  if (name === "vb") return "vb";
  if (name === "mom") return "mom";
  return null;
};

// 판단 기준 가격이 무엇인지 — 이동평균은 평균, 모멘텀은 N 전 종가
export const referenceLabel = (spec: string, group: MarketGroup) => {
  const [name, arg] = spec.split("-");
  if (name === "mom") return `${months(Number(arg), group)}개월 전`;
  return "평균";
};
