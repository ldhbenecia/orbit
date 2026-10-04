# 작업 일지

## 위치

- `docs/progress/README.md` — 단계별 진행률 표
- `docs/progress/YYYY-MM-DD-<slug>.md` — 작업 단위 일지 (같은 날 같은 slug 는 이어쓰기)

## 언제

- 작업 시작: 새 일지
- sub-task 완료: "완료"에 즉시 추가
- 단계 완료: README 표 갱신 (✅ + 날짜)

## 형식

```markdown
# YYYY-MM-DD — <slug>

> 단계: **N — <제목>**
> 상태: 진행 중 | 완료

## 완료
## 진행 중
## 배운 것
## 시행착오 / 결정
## 다음
```

"배운 것"에는 이번 작업에서 처음 다룬 퀀트 개념을 한두 줄로 (→ [learning-mode](learning-mode.md)). 장기 결정은 ADR 로.

커밋: `docs(progress): YYYY-MM-DD-<slug>` / `docs(progress): update <slug>`
