import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from orbit.marketdata.instruments import NEW_YORK, SEOUL, load_universe, market_key
from orbit.marketdata.names import InstrumentName, load_names, save_names

# 예시 종목 — 실제 사용자 목록은 로컬 설정에만
CONFIG = """
dashboard:
  - symbol: SPY
  - symbol: "069500"
    dca: true
    next_open:
      proxy: SPY
      nav: {source: tiger, fund: KR7000000000}
watchlist:
  지수: [SPY, QQQ]
  기타: [BRK.B]
"""


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "markets.local.yaml"
    path.write_text(text)
    return path


def test_종목코드_모양으로_거래소를_정함() -> None:
    assert market_key("SPY") == ("US-SPY", NEW_YORK)
    assert market_key("BRK.B") == ("US-BRK.B", NEW_YORK)
    assert market_key("069500") == ("KRX-069500", SEOUL)
    assert market_key("0000A0") == ("KRX-0000A0", SEOUL)
    with pytest.raises(ValueError):
        market_key("spy")


def test_대시보드와_관심_종목을_합쳐_읽음(tmp_path: Path) -> None:
    universe = load_universe(_write(tmp_path, CONFIG))

    assert universe.markets == ["US-SPY", "KRX-069500", "US-QQQ", "US-BRK.B"]
    spy, etf, qqq, _ = universe.instruments
    assert spy.dashboard and spy.sector == "지수" and not spy.dca
    assert etf.dca and etf.next_open is not None and etf.next_open.proxy == "SPY"
    assert etf.next_open.nav == ("tiger", "KR7000000000")
    assert not qqq.dashboard and qqq.sector == "지수"


def test_설정이_없거나_깨지면_코인만(tmp_path: Path) -> None:
    assert load_universe(tmp_path / "없음.yaml").instruments == ()
    assert load_universe(_write(tmp_path, "dashboard: [깨짐")).instruments == ()
    # 따옴표 없이 쓴 국내 코드가 숫자로 읽혀 자릿수가 깨지면 거부
    assert load_universe(_write(tmp_path, "dashboard:\n  - symbol: 012345\n")).instruments == ()


def test_이름_캐시는_다시_받으면_덮어씀(tmp_path: Path) -> None:
    conn = sqlite3.connect(tmp_path / "orbit.sqlite")
    now = datetime(2026, 10, 17, tzinfo=UTC)

    save_names(conn, [InstrumentName("US-SPY", "SPY", "옛 이름", "AMEX", "USD")], now)
    save_names(conn, [InstrumentName("US-SPY", "SPY", "SPY", "NYSE", "USD")], now)

    assert load_names(conn)["US-SPY"].name == "SPY"


def test_관심_종목은_설정에_적은_분야_순서대로(tmp_path: Path) -> None:
    # 대시보드 종목이 뒤쪽 분야에 있어도 분야 순서는 설정 순서
    config = """
dashboard:
  - symbol: CCC
watchlist:
  첫째: [AAA]
  둘째: [CCC, BBB]
"""
    universe = load_universe(_write(tmp_path, config))

    assert [(i.symbol, i.sector) for i in universe.watchlist()] == [
        ("AAA", "첫째"),
        ("CCC", "둘째"),
        ("BBB", "둘째"),
    ]
