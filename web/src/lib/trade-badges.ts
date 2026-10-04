import type {
  IChartApi,
  IPrimitivePaneRenderer,
  IPrimitivePaneView,
  ISeriesApi,
  ISeriesPrimitive,
  SeriesAttachedParameter,
  Time,
} from "lightweight-charts";

export type Badge = {
  time: string; // 막대 시작일
  side: "buy" | "sell";
  count: number;
  high: number; // 매도 배지는 고가 위, 매수 배지는 저가 아래
  low: number;
};

type Colors = { buy: string; sell: string; text: string; font: string };
type Target = Parameters<IPrimitivePaneRenderer["draw"]>[0];

const MAX_RADIUS = 8;
const MIN_LETTER_RADIUS = 5.5; // 이보다 작으면 글자가 안 읽혀 점으로
const GAP = 4; // 막대 끝과 배지 사이

// 토스증권 "구매·판매 표시" 처럼 동그란 배지 안에 B·S — 기본 마커는 글자를 도형 밖에 그려 촘촘하면 겹침
export class TradeBadges implements ISeriesPrimitive<Time> {
  private chart: IChartApi | null = null;
  private series: ISeriesApi<"Candlestick"> | null = null;
  private requestUpdate: (() => void) | null = null;
  private badges: Badge[] = [];
  private readonly view: IPrimitivePaneView;

  constructor(private readonly colors: Colors) {
    const renderer: IPrimitivePaneRenderer = {
      draw: (target) => this.draw(target),
    };
    this.view = { renderer: () => renderer, zOrder: () => "top" };
  }

  attached({ chart, series, requestUpdate }: SeriesAttachedParameter<Time>) {
    this.chart = chart as IChartApi;
    this.series = series as ISeriesApi<"Candlestick">;
    this.requestUpdate = requestUpdate;
  }

  detached() {
    this.chart = null;
    this.series = null;
    this.requestUpdate = null;
  }

  setBadges(badges: Badge[]) {
    this.badges = badges;
    this.requestUpdate?.();
  }

  paneViews() {
    return [this.view];
  }

  private draw(target: Target) {
    const chart = this.chart;
    const series = this.series;
    if (!chart || !series || this.badges.length === 0) return;
    const timeScale = chart.timeScale();
    const radius = Math.min(MAX_RADIUS, timeScale.options().barSpacing * 0.45);

    target.useMediaCoordinateSpace(({ context: ctx, mediaSize }) => {
      ctx.font = `700 ${Math.round(radius * 1.25)}px ${this.colors.font}`;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      for (const b of this.badges) {
        const x = timeScale.timeToCoordinate(b.time);
        const edge = series.priceToCoordinate(
          b.side === "buy" ? b.low : b.high,
        );
        // 매매가 수천 건이라 화면 밖 배지는 매 프레임 그리지 않음
        if (
          x === null ||
          edge === null ||
          x < -MAX_RADIUS * 3 ||
          x > mediaSize.width + MAX_RADIUS * 3
        )
          continue;
        const y = b.side === "buy" ? edge + GAP + radius : edge - GAP - radius;
        const label = `${b.side === "buy" ? "B" : "S"}${b.count > 1 ? b.count : ""}`;
        const letters = radius >= MIN_LETTER_RADIUS;
        const half = letters
          ? Math.max(radius, ctx.measureText(label).width / 2 + radius * 0.5)
          : radius * 0.6;

        ctx.fillStyle = b.side === "buy" ? this.colors.buy : this.colors.sell;
        ctx.beginPath();
        ctx.roundRect(
          x - half,
          y - (letters ? radius : half),
          half * 2,
          (letters ? radius : half) * 2,
          radius,
        );
        ctx.fill();
        if (letters) {
          ctx.fillStyle = this.colors.text;
          ctx.fillText(label, x, y + 0.5);
        }
      }
    });
  }
}
