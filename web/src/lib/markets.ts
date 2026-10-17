import type { components } from "@/lib/api";
import type { Currency } from "@/lib/format";

export type MarketGroup = "coin" | "stock";

export type MarketInfo = {
  market: string; // 엔진 마켓 키
  name: string;
  group: MarketGroup;
  currency: Currency;
  source: string; // 시세 출처 — 화면 하단 설명
  core: boolean; // 매달 적립하는 종목 — 보유/현금 신호 대신 적립식 분석
  nextOpen: boolean; // 국내 상장 해외 ETF 다음 개장 추정 대상
  dashboard: boolean; // 맨 위 타일
};

export const GROUPS: readonly { value: MarketGroup; label: string }[] = [
  { value: "coin", label: "코인" },
  { value: "stock", label: "주식" },
];

// README 캡처용 가상 데이터 화면 — 예시 이름은 엔진이 붙이고, 웹은 표시와 마켓 코드 숨김만
export const DEMO = process.env.NEXT_PUBLIC_ORBIT_DEMO === "1";

// 종목 목록은 엔진(로컬 설정)에서 — 레포에 내 종목이 드러나지 않게 웹에는 목록을 두지 않음
export const toMarketInfo = (m: components["schemas"]["MarketOut"]): MarketInfo => ({
  market: m.market,
  name: m.name,
  group: m.group,
  currency: m.currency,
  source: DEMO ? "가상 데이터" : m.group === "coin" ? "업비트 원화" : "토스증권 (수정주가)",
  core: m.dca ?? false,
  nextOpen: m.next_open ?? false,
  dashboard: m.dashboard,
});

// 엔진에 닿지 않을 때 — 정책상 코인은 BTC·ETH 고정
export const COIN_FALLBACK: readonly MarketInfo[] = [
  ["KRW-BTC", "비트코인"],
  ["KRW-ETH", "이더리움"],
].map(([market, name], i) => ({
  market,
  name: DEMO ? `예시 코인 ${String.fromCharCode(65 + i)}` : name,
  group: "coin",
  currency: "KRW",
  source: DEMO ? "가상 데이터" : "업비트 원화",
  core: false,
  nextOpen: false,
  dashboard: true,
}));

export const findMarket = (markets: readonly MarketInfo[], value: string | string[] | undefined): MarketInfo =>
  markets.find((m) => m.market === value) ?? markets[0];
