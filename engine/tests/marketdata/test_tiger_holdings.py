from decimal import Decimal

from orbit.marketdata.tiger_holdings import parse_holdings

# 운용사 구성 종목 표 응답 모양 — 값은 예시
PAGE = """
<!-- 변동없을때 -->
         <tr data-tot-cnt="3">
        <td>
                    RKLB US EQUITY</td>
                <td>Rocket Lab Corp</td>
                <td>
                    521.88</td>
                <td>49,663,810</td>
                            <td>
                    13.61</td>
                <td>
                    <div class="color-down"><span class="blind">하락</span>-0.04</div>
                    </td>
            </tr>
<tr data-tot-cnt="3">
        <td>
                    BRK/B US EQUITY</td>
                <td>Berkshire Hathaway Inc</td>
                <td>1</td>
                <td>1,000</td>
                <td>
                    0.02</td>
                <td><div class="color-none"><span class="blind">없음</span>-</div></td>
            </tr>
<tr data-tot-cnt="3">
        <td>
                    KRD010010001</td>
                <td>원화예금</td>
                <td>1,579,809</td>
                <td>1,579,809</td>
                <td>
                    0.43</td>
                <td><div class="color-none"><span class="blind">없음</span>-</div></td>
            </tr>
"""


def test_구성_종목_표에서_심볼과_비중을_읽음() -> None:
    rocket, berkshire, cash = parse_holdings(PAGE)

    assert (rocket.symbol, rocket.weight) == ("RKLB", Decimal("0.1361"))
    assert rocket.name == "Rocket Lab Corp"
    assert not rocket.is_cash
    # 토스 심볼 규칙(영문·숫자·.·-)에 없는 표기는 추측해 바꾸지 않고 시세 없는 종목으로 둠
    assert berkshire.symbol is None and not berkshire.is_cash
    assert (cash.symbol, cash.is_cash, cash.weight) == (None, True, Decimal("0.0043"))
