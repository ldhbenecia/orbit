from decimal import Decimal
from pathlib import Path

from orbit.trading.config import Mode, load_config

VALID = """
mode: dry-run
budget_krw: 500000
limits:
  max_order_krw: 200000
  max_orders_per_day: 2
rules:
  - market: KRW-BTC
    strategy: ma-120
    weight: 0.6
  - market: KRW-ETH
    strategy: ma-60
    weight: 0.4
"""


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "orbit.local.yaml"
    path.write_text(text)
    return path


def test_설정을_Decimal_로_읽음(tmp_path: Path) -> None:
    config = load_config(_write(tmp_path, VALID))

    assert config is not None
    assert config.mode is Mode.DRY_RUN
    assert config.budget_krw == Decimal(500000)
    assert [r.slot for r in config.rules] == ["KRW-BTC:ma-120", "KRW-ETH:ma-60"]
    assert config.rules[0].budget(config.budget_krw) == Decimal(300000)


def test_설정이_없거나_깨지면_아무것도_하지_않음(tmp_path: Path) -> None:
    assert load_config(tmp_path / "없음.yaml") is None
    assert load_config(_write(tmp_path, "mode: [깨짐")) is None


def test_실거래_모드라고_써도_dry_run_으로(tmp_path: Path) -> None:
    # 실거래 경로가 아직 없음 — 설정 한 줄로 실주문이 나가지 않게
    config = load_config(_write(tmp_path, VALID.replace("mode: dry-run", "mode: live")))

    assert config is not None and config.mode is Mode.DRY_RUN


def test_허용_밖_종목_돌파형_규칙_비중_초과는_거부(tmp_path: Path) -> None:
    assert load_config(_write(tmp_path, VALID.replace("KRW-ETH", "KRW-XRP"))) is None
    assert load_config(_write(tmp_path, VALID.replace("ma-60", "vb-0.5"))) is None
    assert load_config(_write(tmp_path, VALID.replace("weight: 0.4", "weight: 0.5"))) is None
    assert (
        load_config(_write(tmp_path, VALID.replace("budget_krw: 500000", "budget_krw: -1"))) is None
    )
