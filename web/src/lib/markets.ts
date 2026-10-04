import type { Currency } from "@/lib/format";

export type MarketGroup = "coin" | "stock";

export type MarketInfo = {
  market: string; // 엔진 마켓 키
  name: string;
  group: MarketGroup;
  currency: Currency;
  source: string; // 시세 출처 — 화면 하단 설명
  core?: boolean; // 사용자가 다른 계좌에서 매달 적립하는 코어 ETF — 보유/현금 신호 대신 적립식 분석
};

export const GROUPS: readonly { value: MarketGroup; label: string }[] = [
  { value: "coin", label: "코인" },
  { value: "stock", label: "미국주식" },
];

// 정책상 코인은 BTC·ETH 만. 주식 종목코드는 토스 종목 정보로 확인한 값
export const MARKETS: readonly MarketInfo[] = [
  { market: "KRW-BTC", name: "비트코인", group: "coin", currency: "KRW", source: "업비트 원화" },
  { market: "KRW-ETH", name: "이더리움", group: "coin", currency: "KRW", source: "업비트 원화" },
  { market: "US-QQQ", name: "QQQ", group: "stock", currency: "USD", source: "토스증권 (수정주가)" },
  { market: "US-SPY", name: "SPY", group: "stock", currency: "USD", source: "토스증권 (수정주가)" },
  { market: "KRX-367380", name: "ACE 미국나스닥100", group: "stock", currency: "KRW", source: "토스증권 (수정주가)", core: true },
  { market: "KRX-360750", name: "TIGER 미국S&P500", group: "stock", currency: "KRW", source: "토스증권 (수정주가)", core: true },
];

export const findMarket = (value: string | string[] | undefined): MarketInfo =>
  MARKETS.find((m) => m.market === value) ?? MARKETS[0];

export const marketsOf = (group: MarketGroup) => MARKETS.filter((m) => m.group === group);
