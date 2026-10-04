// 정책상 코인은 BTC·ETH 만
export const COIN_MARKETS = [
  { market: "KRW-BTC", name: "비트코인", symbol: "BTC" },
  { market: "KRW-ETH", name: "이더리움", symbol: "ETH" },
] as const;

export type CoinMarket = (typeof COIN_MARKETS)[number];

export const findCoinMarket = (value: string | string[] | undefined): CoinMarket =>
  COIN_MARKETS.find((m) => m.market === value) ?? COIN_MARKETS[0];
