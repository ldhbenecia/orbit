from orbit.cli import _STANCE_LABEL
from orbit.signals.today import Stance


def test_신호_상태가_늘면_터미널_표시_이름도_정해야_함() -> None:
    # 상태를 추가하고 이름을 빼먹으면 orbit signal 이 그 상태에서 KeyError
    assert set(_STANCE_LABEL) == set(Stance)
