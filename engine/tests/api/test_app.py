from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient

from orbit.api.app import create_app
from orbit.marketdata.candle import Candle
from orbit.marketdata.store import CandleStore

D = datetime(2024, 1, 1, tzinfo=UTC)


def _client(tmp_path: Path) -> TestClient:
    db = tmp_path / "orbit.sqlite"
    store = CandleStore.open(db)
    store.upsert(
        [
            Candle("KRW-BTC", D, *(Decimal(v) for v in ("1", "3", "0.5", "115216000.1", "2", "9"))),
            Candle("KRW-ETH", D, *(Decimal("1") for _ in range(6))),
        ]
    )
    store.close()
    return TestClient(create_app(lambda: CandleStore.open(db)))


def test_종목별_일봉을_돌려줌(tmp_path: Path) -> None:
    body = _client(tmp_path).get("/candles", params={"market": "KRW-BTC"}).json()

    assert len(body) == 1
    assert body[0]["start"] == "2024-01-01T00:00:00Z"


def test_가격은_문자열로_내보내_정밀도_유지(tmp_path: Path) -> None:
    body = _client(tmp_path).get("/candles").json()

    assert body[0]["close"] == "115216000.1"
