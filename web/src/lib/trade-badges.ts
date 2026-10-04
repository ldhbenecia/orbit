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

// 토스증권처럼 확대·축소와 무관하게 같은 크기 — 막대 간격에 맞추면 기본 화면에서 글자가 안 들어감
const SIZE = 16; // 배지 높이·최소 너비
const CORNER = 4;
const TAIL = 4; // 막대 쪽을 가리키는 꼬리 높이
const GAP = 2; // 막대 끝과 꼬리 사이

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

    target.useMediaCoordinateSpace(({ context: ctx, mediaSize }) => {
      ctx.font = `700 11px ${this.colors.font}`;
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
          x < -SIZE ||
          x > mediaSize.width + SIZE
        )
          continue;

        const label = `${b.side === "buy" ? "B" : "S"}${b.count > 1 ? b.count : ""}`;
        const width = Math.max(SIZE, ctx.measureText(label).width + 8);
        const down = b.side === "buy"; // 매수는 막대 아래로, 매도는 위로
        const tip = down ? edge + GAP : edge - GAP; // 꼬리 끝
        const boxTop = down ? tip + TAIL : tip - TAIL - SIZE;

        ctx.fillStyle = down ? this.colors.buy : this.colors.sell;
        ctx.beginPath();
        ctx.roundRect(x - width / 2, boxTop, width, SIZE, CORNER);
        ctx.moveTo(x - TAIL, down ? boxTop : boxTop + SIZE);
        ctx.lineTo(x, tip);
        ctx.lineTo(x + TAIL, down ? boxTop : boxTop + SIZE);
        ctx.closePath();
        ctx.fill();

        ctx.fillStyle = this.colors.text;
        ctx.fillText(label, x, boxTop + SIZE / 2 + 0.5);
      }
    });
  }
}
