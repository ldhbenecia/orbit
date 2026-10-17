import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import httpx
import uvicorn
from fastapi.testclient import TestClient

from orbit.api.app import create_app
from orbit.backtest.engine import DEFAULT_CONFIG, Funding, run_backtest
from orbit.backtest.metrics import compute_metrics
from orbit.backtest.runs import RunSpec, save_run
from orbit.marketdata.candle import Candle
from orbit.marketdata.instruments import NEW_YORK, SEOUL, Instrument, NextOpenSpec, Universe
from orbit.marketdata.names import InstrumentName, save_names
from orbit.marketdata.store import CandleStore
from orbit.marketdata.upbit_ticker import Ticker
from orbit.strategies.registry import build_strategy
from tests.backtest.test_engine import candles

D = datetime(2024, 1, 1, tzinfo=UTC)


def _client(tmp_path: Path) -> TestClient:
    db = tmp_path / "orbit.sqlite"
    store = CandleStore.open(db)
    store.upsert(
        [
            Candle("KRW-BTC", D, *(Decimal(v) for v in ("1", "3", "1", "115216000", "0.5"))),
            Candle("KRW-ETH", D, *(Decimal("1") for _ in range(5))),
        ],
        fetched_at=D,
    )
    store.close()
    return TestClient(create_app(lambda: sqlite3.connect(db)))


def test_종목별_일봉을_돌려줌(tmp_path: Path) -> None:
    body = _client(tmp_path).get("/candles", params={"market": "KRW-BTC"}).json()

    assert len(body) == 1
    assert body[0]["start"] == "2024-01-01T00:00:00Z"


def test_가격은_문자열로_내보내_정밀도_유지(tmp_path: Path) -> None:
    body = _client(tmp_path).get("/candles").json()

    assert body[0]["close"] == "115216000"
    assert body[0]["volume"] == "0.50000000"


def test_막대_단위를_고르면_묶어서_돌려줌(tmp_path: Path) -> None:
    body = _client(tmp_path).get("/candles", params={"interval": "month"}).json()

    assert body[0]["start"] == "2024-01-01T00:00:00Z"


def test_모르는_막대_단위는_거부(tmp_path: Path) -> None:
    assert _client(tmp_path).get("/candles", params={"interval": "minute"}).status_code == 422


def test_실서버_동시_요청에도_DB_연결이_스레드를_넘지_않음(tmp_path: Path) -> None:
    # TestClient 는 요청마다 루프를 새로 만들어 재현 안 됨 — 실제 uvicorn 한 루프에 동시 요청
    db = tmp_path / "orbit.sqlite"
    _client(tmp_path)
    app = create_app(lambda: sqlite3.connect(db))
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.01)
    port = server.servers[0].sockets[0].getsockname()[1]

    try:
        with (
            httpx.Client(base_url=f"http://127.0.0.1:{port}") as http,
            ThreadPoolExecutor(12) as pool,
        ):
            codes = list(
                pool.map(
                    lambda iv: http.get("/candles", params={"interval": iv}).status_code,
                    ["day", "week", "month"] * 50,
                )
            )
    finally:
        server.should_exit = True
        thread.join()

    assert set(codes) == {200}


def test_오늘의_규칙_신호(tmp_path: Path) -> None:
    db = tmp_path / "orbit.sqlite"
    store = CandleStore.open(db)
    days = [D + timedelta(days=i) for i in range(210)]
    prices = [Decimal(1000 + i) for i in range(len(days))]  # 매일 오름 → 이동평균 위
    store.upsert(
        [Candle("KRW-BTC", d, p, p, p, p, Decimal(1)) for d, p in zip(days, prices, strict=True)],
        fetched_at=D,
    )
    store.close()
    ticker = Ticker(
        day=days[-1] + timedelta(days=1),
        open=Decimal(2000),
        high=Decimal(2001),
        price=Decimal(2000),
    )
    client = TestClient(create_app(lambda: sqlite3.connect(db), get_ticker=lambda market: ticker))

    body = client.get("/signals").json()

    assert body["as_of"] == days[-1].strftime("%Y-%m-%dT%H:%M:%SZ")
    assert body["price"] == "2000"
    by_name = {s["strategy"]: s for s in body["signals"]}
    assert by_name["ma-120"]["stance"] == "hold"
    assert by_name["ma-120"]["status"] == "실험 중"
    assert by_name["vb-0.5"]["trigger"] == "2000"  # 전날 변동폭 0 (시·고·저·종 같음)


def test_백테스트_목록과_매매(tmp_path: Path) -> None:
    db = tmp_path / "orbit.sqlite"
    conn = sqlite3.connect(db)
    prices = candles([(1_000_000, 1_000_000 + i % 4 * 50_000) for i in range(30)])
    spec = RunSpec(
        market="KRW-BTC",
        strategy="ma-3",
        params={"window": "3"},
        start=prices[1].start,
        end=prices[-1].start,
        funding=Funding(initial=Decimal(1_000_000), monthly=Decimal(0)),
        config=DEFAULT_CONFIG,
        code_version="abc1234",
    )
    result = run_backtest(prices, build_strategy("ma-3")[0], spec.funding)
    run_id = save_run(conn, spec, compute_metrics(result), result.trades, D)
    conn.close()
    client = TestClient(create_app(lambda: sqlite3.connect(db)))

    runs = client.get("/backtests").json()
    trades = client.get(f"/backtests/{run_id}/trades").json()

    assert [(r["id"], r["strategy"]) for r in runs] == [(run_id, "ma-3")]
    assert len(trades) == len(result.trades)
    assert trades[0]["side"] == "buy"
    assert int(trades[0]["price"]) % 1000 == 0


def test_최근_N개만_돌려주고_전체_범위는_요약으로(tmp_path: Path) -> None:
    db = tmp_path / "orbit.sqlite"
    store = CandleStore.open(db)
    days = [D + timedelta(days=i) for i in range(10)]
    store.upsert(
        [
            Candle("KRW-BTC", d, Decimal(1), Decimal(1), Decimal(1), Decimal(1), Decimal(1))
            for d in days
        ],
        fetched_at=D,
    )
    store.close()
    client = TestClient(create_app(lambda: sqlite3.connect(db)))

    recent = client.get("/candles", params={"limit": 3}).json()
    summary = client.get("/candles/summary").json()

    assert [c["start"][:10] for c in recent] == [d.date().isoformat() for d in days[-3:]]
    assert (summary["first"][:10], summary["count"]) == ("2024-01-01", 10)
    assert client.get("/candles", params={"limit": 0}).status_code == 422


def test_적립식_분석(tmp_path: Path) -> None:
    db = tmp_path / "orbit.sqlite"
    store = CandleStore.open(db)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    days = [
        start + timedelta(days=i) for i in range(200) if (start + timedelta(days=i)).weekday() < 5
    ]
    store.upsert(
        [
            Candle("KRX-100000", d, *(Decimal(10_000 + i * 10),) * 4, Decimal(1))
            for i, d in enumerate(days)
        ],
        fetched_at=D,
    )
    store.close()
    app = create_app(
        lambda: sqlite3.connect(db),
        kr_trading_day_for=lambda d: d - timedelta(days=1) if d.day == 25 and d.month == 6 else d,
        today=lambda: date(2026, 6, 10),
    )

    body = TestClient(app).get("/dca", params={"market": "KRX-100000"}).json()

    assert body["next_payday"] == "2026-06-24"  # 6-25 휴장이라 직전 영업일
    assert body["days_until"] == 14
    assert body["holidays_checked"] is True
    assert body["months"] == 6  # 1~6월 — 데이터가 7-17 에서 끝나 7월 적립일은 아직
    assert [p["window"] for p in body["positions"]] == [60, 120]
    assert Decimal(body["return_on_invested"]) > 0  # 계속 오르는 가격


def test_일봉이_추가되거나_고쳐지면_캐시를_쓰지_않고_새로_읽음(tmp_path: Path) -> None:
    db = tmp_path / "orbit.sqlite"
    store = CandleStore.open(db)
    store.upsert([Candle("KRW-BTC", D, *(Decimal(v) for v in ("1", "1", "1", "100", "1")))], D)
    client = TestClient(create_app(lambda: sqlite3.connect(db)))
    assert [c["close"] for c in client.get("/candles").json()] == ["100"]

    # 같은 봉을 다시 받아 값만 바뀜 — 봉 개수·마지막 봉은 그대로
    store.upsert(
        [Candle("KRW-BTC", D, *(Decimal(v) for v in ("1", "1", "1", "200", "1")))],
        D + timedelta(hours=1),
    )
    assert [c["close"] for c in client.get("/candles").json()] == ["200"]

    store.upsert(
        [
            Candle(
                "KRW-BTC", D + timedelta(days=1), *(Decimal(v) for v in ("1", "1", "1", "300", "1"))
            )
        ],
        D + timedelta(hours=2),
    )
    assert [c["close"] for c in client.get("/candles").json()] == ["200", "300"]
    store.close()


def test_다음_개장_추정은_설정한_종목만_계산하고_실패하면_비움(tmp_path: Path) -> None:
    from orbit.estimate.live import NextOpenView
    from orbit.estimate.next_open import NextOpen

    def view(market: str) -> NextOpenView:
        if market == "KRX-200000":
            raise httpx.ConnectError("허용 IP 아님")
        result = NextOpen(
            Decimal(7360), Decimal("7656.6"), Decimal("0.03"), Decimal("0.01"), Decimal("0.0403")
        )
        return NextOpenView(
            state="ready",
            next_open_day=date(2026, 10, 6),
            kr_close_day=date(2026, 10, 2),
            result=result,
        )

    db = tmp_path / "orbit.sqlite"
    spec = NextOpenSpec(proxy="SPY")
    universe = Universe(
        (
            Instrument("KRX-100000", "100000", SEOUL, dashboard=True, next_open=spec),
            Instrument("KRX-200000", "200000", SEOUL, dashboard=True, next_open=spec),
            Instrument("KRX-300000", "300000", SEOUL, dashboard=True),  # 추정 설정 없음
        )
    )
    client = TestClient(create_app(lambda: sqlite3.connect(db), next_open=view, universe=universe))

    body = client.get("/next-open", params={"market": "KRX-100000"}).json()
    assert (body["estimate"], body["next_open_day"]) == ("7656.6", "2026-10-06")
    assert client.get("/next-open", params={"market": "KRX-300000"}).json() is None
    assert client.get("/next-open", params={"market": "KRX-200000"}).json() is None


def test_종목_목록은_코인_다음_설정_순서_이름을_못_받았으면_종목코드(tmp_path: Path) -> None:
    db = tmp_path / "orbit.sqlite"
    conn = sqlite3.connect(db)
    save_names(conn, [InstrumentName("US-SPY", "SPY", "SPDR S&P 500", "NYSE", "USD")], D)
    conn.close()
    universe = Universe(
        (
            Instrument("US-SPY", "SPY", NEW_YORK, dashboard=True, sector="지수"),
            Instrument("KRX-100000", "100000", SEOUL, dashboard=True, dca=True),
            Instrument("US-QQQ", "QQQ", NEW_YORK, sector="지수"),
        )
    )

    body = (
        TestClient(create_app(lambda: sqlite3.connect(db), universe=universe))
        .get("/markets")
        .json()
    )

    assert [m["market"] for m in body] == ["KRW-BTC", "KRW-ETH", "US-SPY", "KRX-100000", "US-QQQ"]
    by = {m["market"]: m for m in body}
    assert by["US-SPY"]["name"] == "SPDR S&P 500" and by["US-SPY"]["currency"] == "USD"
    assert by["KRX-100000"]["name"] == "100000" and by["KRX-100000"]["dca"] is True
    assert by["US-QQQ"]["dashboard"] is False and by["US-QQQ"]["sector"] == "지수"


def test_가상_데이터_DB_는_실제_이름을_하나도_내보내지_않음(tmp_path: Path) -> None:
    from orbit.marketdata.demo import demo_names

    db = tmp_path / "orbit.sqlite"
    universe = Universe(
        (
            Instrument("US-SPY", "SPY", NEW_YORK, dashboard=True),
            Instrument("US-QQQ", "QQQ", NEW_YORK, sector="지수"),
        ),
        ("지수",),
    )
    conn = sqlite3.connect(db)
    save_names(conn, demo_names(universe), D)  # orbit demo-data 가 넣는 이름
    conn.close()

    body = (
        TestClient(create_app(lambda: sqlite3.connect(db), universe=universe))
        .get("/markets")
        .json()
    )

    names = [m["name"] for m in body]
    assert names == ["예시 코인 A", "예시 코인 B", "예시 종목 1", "예시 관심 종목 1"]
    assert not any(real in " ".join(names) for real in ("비트코인", "이더리움", "SPY", "QQQ"))


def _stock(market: str, closes: list[int]) -> list[Candle]:
    start = datetime(2025, 1, 1, tzinfo=UTC)
    return [
        Candle(
            market,
            start + timedelta(days=i),
            Decimal(c),
            Decimal(c),
            Decimal(c),
            Decimal(c),
            Decimal(1),
        )
        for i, c in enumerate(closes)
    ]


def test_관심_종목은_분야_순서대로_고점_대비와_추세를_보여줌(tmp_path: Path) -> None:
    db = tmp_path / "orbit.sqlite"
    store = CandleStore.open(db)
    # 오르다 꺾임: 100 → 300 까지 오른 뒤 240 — 52주 고점 대비 −20%
    rising = list(range(100, 301, 1)) + [280, 260, 240]
    falling = list(range(300, 99, -1))
    store.upsert(_stock("US-AAA", rising) + _stock("US-BBB", falling), fetched_at=D)
    store.close()
    universe = Universe(
        (
            Instrument("US-AAA", "AAA", NEW_YORK, sector="테크"),
            Instrument("US-BBB", "BBB", NEW_YORK, sector="방산"),
            Instrument("US-CCC", "CCC", NEW_YORK, sector="테크"),  # 일봉 없음
            Instrument("US-DDD", "DDD", NEW_YORK, dashboard=True),  # 분야 없음 — 관심 종목 아님
        ),
        ("테크", "방산"),
    )

    body = (
        TestClient(create_app(lambda: sqlite3.connect(db), universe=universe))
        .get("/watchlist")
        .json()
    )

    assert [(r["market"], r["sector"]) for r in body] == [
        ("US-AAA", "테크"),
        ("US-CCC", "테크"),
        ("US-BBB", "방산"),
    ]
    aaa, ccc, bbb = body
    assert Decimal(aaa["from_high"]) == Decimal("-0.2")  # 240 ÷ 300 − 1
    assert Decimal(aaa["change"]) == Decimal(240) / Decimal(260) - 1
    # 추세 표시는 신호에 쓰는 이동평균 규칙 함수의 판단과 같아야 함 (두 계산 일치)
    history = _stock("US-AAA", rising)
    expected = [build_strategy(f"ma-{w}")[0](history).target_weight > 0 for w in (60, 120, 200)]
    assert [(t["window"], t["above"]) for t in aaa["trend"]] == list(
        zip((60, 120, 200), expected, strict=True)
    )
    assert expected == [False, False, True]  # 꺾인 직후 — 짧은 평균 아래, 긴 평균 위
    assert all(t["above"] is False for t in bbb["trend"])  # 계속 내린 종목은 모두 평균 아래
    assert ccc["close"] is None and ccc["trend"] == []
    assert {r["currency"] for r in body} == {"USD"}


def test_규칙_검증은_기록이_없으면_비움(tmp_path: Path) -> None:
    db = tmp_path / "orbit.sqlite"
    client = TestClient(create_app(lambda: sqlite3.connect(db)))

    assert client.get("/rule-checks", params={"market": "KRW-BTC"}).json() is None


def test_가상_장부가_비어_있으면_빈_목록(tmp_path: Path) -> None:
    db = tmp_path / "orbit.sqlite"
    client = TestClient(create_app(lambda: sqlite3.connect(db)))

    assert client.get("/wallet").json() == {"mode": "dry-run", "slots": []}
