import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import httpx
import uvicorn
from fastapi.testclient import TestClient

from orbit.api.app import create_app
from orbit.marketdata.candle import Candle
from orbit.marketdata.store import CandleStore
from orbit.marketdata.upbit_ticker import Ticker

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
    return TestClient(create_app(lambda: CandleStore.open(db)))


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
    app = create_app(lambda: CandleStore.open(db))
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
    client = TestClient(create_app(lambda: CandleStore.open(db), get_ticker=lambda market: ticker))

    body = client.get("/signals").json()

    assert body["as_of"] == days[-1].strftime("%Y-%m-%dT%H:%M:%SZ")
    assert body["price"] == "2000"
    by_name = {s["strategy"]: s for s in body["signals"]}
    assert by_name["ma-120"]["stance"] == "hold"
    assert by_name["ma-120"]["status"] == "실험 중"
    assert by_name["vb-0.5"]["trigger"] == "2000"  # 전날 변동폭 0 (시·고·저·종 같음)
