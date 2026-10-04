# 결정 기록 (ADR)

## 써야 하는 경우

- 기술 선택 (언어, 라이브러리, 거래소 API)
- 돈·리스크 정책 (예산 격리 방식, 한도 구조, 주문 방식)
- **전략 채택·기각·파라미터 확정** — 어떤 백테스트 근거로 정했는지
- 아키텍처 (책임 위치, 데이터 흐름)
- 6개월 뒤 "왜 이렇게 했지?"가 떠오르지 않을 결정

## 안 써도 되는 경우

자명한 구현 선택, 임시 실험 (실험은 `research/` 노트북에)

## 파일

`docs/decisions/NNNN-kebab-case.md` (4자리, 순차). 머지된 ADR 은 삭제하지 않고 새 ADR 로 supersede.

## 템플릿

```markdown
# NNNN. <결정 제목>

- 상태: proposed / accepted / superseded by NNNN
- 작성일: YYYY-MM-DD

## 맥락
## 결정
## 대안
## 결과
```

작성은 `new-decision` 스킬. `docs/decisions/` 는 로컬 전용이라 커밋하지 않는다
