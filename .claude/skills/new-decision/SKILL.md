---
name: new-decision
description: orbit ADR 작성 — 다음 번호 계산, 템플릿 채우기, 관련 ADR supersede 처리
---

# ADR 작성

## 인자

$ARGUMENTS — 결정 주제

## 절차

1. `docs/decisions/` 에서 마지막 번호 확인 → +1 (4자리)
2. 관련 기존 ADR 검색. 뒤집는 결정이면 기존 ADR 상태를 `superseded by NNNN` 으로
3. [decisions-workflow](../../rules/decisions-workflow.md) 템플릿으로 작성
   - 맥락: 왜 지금 결정이 필요한지, 제약
   - 결정: 단호하게 한 문단
   - 대안: 고려했던 것과 버린 이유
   - 결과: 트레이드오프, 후속 작업
   - 전략 채택 ADR 이면 근거 백테스트 조건(기간·수수료·데이터 소스)과 핵심 수치 포함
4. 상태: 사용자가 확정하면 `accepted`, 아니면 `proposed`
5. `docs/decisions/` 는 로컬 전용(gitignore)이라 커밋하지 않는다. 결정이 룰을 바꾸면 `.claude/rules/` 갱신을 공개 커밋으로 (ADR 번호는 인용하지 않음)
