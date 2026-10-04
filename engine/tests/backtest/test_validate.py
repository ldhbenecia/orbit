import sqlite3
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from orbit.backtest.validate import check_rules, latest_checks, periods, save_checks, specs_for
from tests.backtest.test_engine import candles


def test_코인은_변동성_돌파까지_주식은_이동평균만() -> None:
    assert "vb-0.5" in specs_for("KRW-BTC") and "ma-120" in specs_for("KRW-BTC")
    assert not any(s.startswith("vb") for s in specs_for("US-QQQ"))
    assert specs_for("US-QQQ")[0] == "hold"


def test_평가는_가장_긴_이동평균을_계산할_수_있는_날부터_두_기간으로_나눔() -> None:
    history = candles([(100, 100)] * 21)

    whole, first, second = periods(history, warmup=10)

    assert whole[0] == history[11].start and whole[1] == history[-1].start
    assert first[0] == whole[0] and second[1] == whole[1]
    assert first[1] < second[0]


def test_기간별로_기준가_수익과_낙폭을_따로_셈() -> None:
    # 앞 절반은 100 → 200 으로 오르고, 뒤 절반은 200 → 100 으로 내림
    up = [(100 + i * 10, 100 + (i + 1) * 10) for i in range(10)]
    down = [(200 - i * 10, 200 - (i + 1) * 10) for i in range(10)]
    history = candles([(100, 100)] * 3 + up + down)

    rows = {(r.strategy, r.period): r for r in check_rules("KRW-BTC", history, ["hold"], warmup=2)}

    assert rows[("hold", "first")].cagr > 0
    assert rows[("hold", "second")].cagr < 0
    assert rows[("hold", "second")].mdd < Decimal("-0.4")
    # 단순 보유는 평가 시작 전(판단 준비 기간)에 산 것 — 평가 구간 안의 거래는 없음
    assert rows[("hold", "all")].trades == 0


def test_가장_최근_검증_묶음만_돌려줌(tmp_path: Path) -> None:
    history = candles([(100, 100)] * 3 + [(100 + i, 101 + i) for i in range(20)])
    rows = check_rules("KRW-BTC", history, ["hold"], warmup=2)
    conn = sqlite3.connect(tmp_path / "orbit.sqlite")

    save_checks(conn, "KRW-BTC", rows, datetime(2026, 10, 1, tzinfo=UTC), "old")
    save_checks(conn, "KRW-BTC", rows[:1], datetime(2026, 10, 4, tzinfo=UTC), "new")
    saved = latest_checks(conn, "KRW-BTC")

    assert saved is not None and saved.code_version == "new"
    assert len(saved.rows) == 1 and saved.rows[0].cagr == round(rows[0].cagr, 6)
    assert latest_checks(conn, "US-QQQ") is None
