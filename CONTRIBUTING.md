# Contributing to superrelease

기여를 환영합니다. superrelease는 **컴파일러 패턴** Claude Code 플러그인이다 — 무거운 `init`이
프로젝트 전용 릴리스 툴킷을 사용자 레포에 렌더한다. 아키텍처·규율의 상세는
[CLAUDE.md](CLAUDE.md)에, 제품 개요는 [README.md](README.md)에 있다.

## Prerequisites

- **Python 3.9+** (표준 라이브러리만 — 생성 스크립트는 무의존이다)
- **Claude Code** — 플러그인 검증(`claude plugin validate`)에 필요
- 테스트 러너는 `unittest`다. pytest·기타 패키지 불필요.

## Dev loop

```bash
# 전체 테스트
python3 -m unittest discover -s tests -q

# 단일 모듈 (tests/__init__.py가 없어 `python3 -m unittest tests.<mod>`는 실패한다)
cd tests && python3 -m unittest test_render_pipeline -v; cd ..

# 플러그인 검증 (PR 전 필수)
claude plugin validate . --strict

# 로컬 플러그인 로드
claude --plugin-dir .
```

### 골든 스냅샷을 바꿨다면

`tests/golden/<name>/expected/**`는 생성물 트리의 전체 스냅샷이다. asset·스킬·템플릿을
바꾸면 골든 불일치는 정상이다:

```bash
python3 tests/update_golden.py
git status --porcelain tests/golden   # 의도한 트리만 바뀌었는지 반드시 확인
```

**의도하지 않은 골든 트리가 바뀌었다면 회귀다** — 대개 조건 블록이 미해당 config에서 0바이트로
collapse되지 않은 경우다. 개행을 `{{#if}}` **안**에 두어라.

## 지켜야 할 규율 (상세는 CLAUDE.md)

- **동결 template dialect** — render.py의 dialect를 확장하지 않는다. 생성 스킬은 기존 문법만 조합.
- **바이트 불변** — 조건 블록은 미해당 config에서 0바이트 collapse → 기존 골든 바이트 동일.
- **자립성** — 생성 스킬은 `.superrelease/`·`.claude/` 상대 경로만 참조하고 플러그인 경로
  (`${CLAUDE_PLUGIN_ROOT}`)는 참조하지 않는다. 렌더된 툴킷은 플러그인 없이 동작해야 한다.
- **스크립트는 무의존** — Python 3.9+ 표준 라이브러리만, exit 0/1/2.
- **엔진은 안정** — 새 기능의 제약은 render 엔진이 아니라 `validate_config`에만 추가.
- **언어** — 코드·에러 메시지는 영어, 생성 문서·init 프로즈·references는 한국어.
- **줄 수** — 생성 SKILL.md ≤150줄, init SKILL.md ≤500줄.

## 커밋·브랜치

- **Conventional Commits** — `feat:` / `fix:` / `docs:` / `test:` / `refactor:` / `chore:`.
  예: `feat: render 검증 — train은 independent 필수`.
- **트렁크 기반(GitHub Flow)** — `main`에서 기능 브랜치를 따서 작업 → PR → 리뷰 → `main` 머지.
  장수 브랜치(gitflow의 `develop`/`release/*`)는 쓰지 않는다.
- PR 전 **전체 테스트 + `claude plugin validate . --strict`** 통과를 확인한다.

## 설계 문서

큰 변경은 `docs/superpowers/specs/`(설계)와 `docs/superpowers/plans/`(구현 계획)에 문서를 남긴다 —
날짜-마일스톤 네이밍(`YYYY-MM-DD-...`).

## 라이선스

기여물은 [MIT License](LICENSE) 하에 배포된다.
