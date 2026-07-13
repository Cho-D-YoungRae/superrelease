# superrelease M3c-3a — release trains (이중 체계 모노레포) 설계

이 문서는 M3c-3의 첫 조각 **M3c-3a**의 설계다. `independent` 모노레포 위에 루트 CalVer **release train**을 얹어, 포함 패키지들의 마지막 릴리스 버전을 한 train 버전으로 스냅샷 고정하고 통합 노트·루트 태그를 내보내는 기능을 추가한다.

베이스 스펙: [2026-07-09-superrelease-plugin-design.md](2026-07-09-superrelease-plugin-design.md) (§4.3 질문 번들 1·2, §6.5 조건부 스킬, §6.7 노트 템플릿 3종, §6.8 config 스키마). 베이스 커밋: main `3d15a71`.

## M3c-3 분해 (참고)

- **M3c-3a (이 문서)**: release trains — 이중 체계 모노레포(루트 CalVer train + 패키지 SemVer).
- **M3c-3b**: 모노레포 backfill(`independent` 확장, scope별 태그 네임스페이스 순회) + M3c-2 backfill 후속 5건(#2~#6). trains와 독립적이므로 별도 계획.

## 배경

`references/monorepo.md`와 `version-schemes.md`가 이미 이중 체계를 서술하고 "M3로 미뤄짐"으로 표시하고 있다: 루트 train은 `2020.0.x`류 CalVer 이름을 쓰고 그 안의 패키지는 각자의 SemVer를 유지한다(Spring Cloud 사례). "이번 train에 어떤 조합의 모듈 버전들이 함께 검증됐는가"를 train 버전 하나로 표현한다. 베이스 스펙 §6.5는 release-train 스킬을 "포함 패키지들의 현재 버전 스냅샷 고정 + 통합 노트(notes-train) + 루트 태그(CalVer)"로 예고했고, §6.8 config에 `repo.train` placeholder 불리언, 트리 §6.1에 `release-train/SKILL.md`(조건부 `repo.train`)·`notes-train.md`를 예고했다. 이 마일스톤이 그 기능을 실동작으로 채운다.

## 확정된 설계 결정

| 결정 | 선택 | 근거 |
|---|---|---|
| 전략 인코딩 | `monorepoStrategy: "independent"` + `train` 객체 (새 strategy 값 없음) | 패키지는 기존 independent 기계 그대로, train은 순수 additive |
| train 버전 모델 | 태그 파생 top-level `train` 객체 (file-less) | SSOT=최신 `train-*` 태그, next-version.py 순수 모드 재사용 → 스크립트 무변경 |
| 스냅샷 대상 | 각 패키지의 **마지막 릴리스(태그) 버전** (tagless는 파일 폴백) | dual-scheme 전형(Maven Spring Cloud)은 릴리스 사이 `-SNAPSHOT` 개발 버전을 파일에 둠 → 태그라야 "검증된 조합"이 정확 |
| train 포함 범위 | 전 패키지 scope (v1, `includes` 부분집합 없음) | YAGNI, 부분집합은 후속 |
| release-pr 지원 | 지원 (M3b 릴리스-PR 프로즈 미러링) | trains는 protected branch 쓰는 엔터프라이즈 모노레포가 주 대상 |
| CalVer 어휘 | 기존 7토큰(`YYYY·YY·0M·MM·0D·DD·MICRO`, MICRO≤1), 기본 `YYYY.MICRO` | next-version.py 무변경, Spring Cloud 3파트는 후속 |

## A. 전략 인코딩 (핵심)

**이중 체계 = `monorepoStrategy: "independent"` + `train` 객체.** 새 strategy 값을 만들지 않는다. 패키지 scope는 기존 independent 기계(changed-packages·scope별 태그·dependents)를 그대로 쓰고, train은 그 위에 순수 additive로 얹힌다.

생성물 조합: `release-monorepo`(패키지 릴리스, 무변경) + `release-notes`(무변경) + **`release-train`(신규, `when: train.enabled`)** + **`notes-train`(신규 템플릿, `when: train.enabled`)**.

## B. config 모델 — top-level `train` 객체

`repo`·`github`·`scopes`의 형제로 추가한다:

```json
"train": {
  "enabled": true,
  "scheme": { "type": "calver", "pattern": "YYYY.MICRO" },
  "tag": { "format": "train-{version}", "annotated": true, "signed": false }
}
```

- **SSOT = 최신 `train-*` 태그** (버전 파일 없음, file-less). 스냅샷은 notes-train 문서에 기록한다.
- 기존 `repo.train` 불리언 placeholder는 이 객체로 **승격**한다 — init config 템플릿에서 `repo.train` 줄을 제거하고 `train` 객체를 추가한다. manifest 게이트 = `train.enabled`. train 아닌 레포는 `train` 객체 부재 → dot-path falsy → 스킬 미생성(기존 조건부 스킬과 동일 메커니즘). 이는 base 스펙 §6.8의 placeholder 불리언을 실체 객체로 구현하는 것으로, 스펙 정합 단계에서 문서화한다.
- CalVer 어휘 한계(`YYYY·YY·0M·MM·0D·DD·MICRO`, MICRO 최대 1회) 때문에 Spring Cloud의 3파트 `2020.0.1`(연도.MINOR.PATCH)은 그대로 표현 불가하다 → `YYYY.MICRO`(`2026.0`, `2026.1`)를 기본으로 제안한다. 설계·references에 이 한계를 명시한다.

## C. render.py 검증 규칙 (유일한 Python 변경)

기존 `validate_config` 패턴에 train 규칙을 추가한다(형제 규칙과 동형):

1. `train`이 truthy(존재)이고 `train.enabled`가 truthy면 `monorepoStrategy == "independent"` 필수 — 아니면 config 오류(exit 1). 단일 레포·fixed·train 조합을 거부한다.
2. `train.enabled` truthy면 `train.scheme.type`은 `"calver"`만 허용 — train 루트는 CalVer 설계. 비-calver면 exit 1.
3. `train.enabled` truthy면 `train.scheme.pattern`(비어있지 않은 문자열)·`train.tag.format`(문자열, `{version}` 포함) 필수 — 누락 시 exit 1.

render.py는 골든-복사 대상이 아니므로 골든 무영향이며, 해당 조합 골든이 신규 `train-monorepo` 하나뿐이라 기존 골든도 불변이다.

## D. `release-train/SKILL.md` (신규 조건부 스킬, ≤150줄, 자립)

hotfix·backfill처럼 조건부로 생성되는 자립 스킬. `.superrelease/`·`.claude/` 상대 경로만 참조한다.

- **description**: 3인칭·pushy·한국어 트리거+영어 키워드·**프로젝트명 포함**. 트리거 예: "train 릴리스, 릴리스 트레인, 통합 릴리스, 루트 릴리스, train 태그 따줘, 이번 train에 뭐 들어가, release train". 패키지 개별 릴리스를 다루는 `release` 스킬과 트리거를 구분한다.
- **§0 대상**: 이 스킬 = **루트 train 릴리스**이며 패키지 개별 릴리스(release 스킬)와 **별개의 릴리스 타입**임을 명시한다. status 모드("이번 train에 뭐 들어가", "다음 train 버전")는 §2~§4만 수행해 스냅샷·다음 버전을 보고하고 멈춘다.
- **§1 preflight**: 현재 브랜치 = `{{repo.defaultBranch}}` / clean working tree / 원격 동기화(`git fetch` 후 `rev-list HEAD..origin/<branch> --count` = 0){{#if github.release}} / gh 인증{{/if}}. 패키지 scope가 mid-release(파일 버전이 anchor보다 높은데 해당 태그 없음)면 경고하고 먼저 정리를 권한다.
- **§2 현재 train 버전**: `git tag --list 'train-*'`(train.tag.format의 prefix 기준) → 버전 순 정렬 → 최신 → prefix strip. 없으면 **첫 train**.
- **§3 다음 train 버전**: `python3 .superrelease/scripts/next-version.py --current <현재> --scheme calver --pattern <train.scheme.pattern> --today <오늘>`. 첫 train은 `--current`를 생략한다(순수 calver 모드가 current 없으면 MICRO=0을 반환 — `calver_next`). LLM 산술 금지, 반드시 스크립트.
- **§4 패키지 버전 스냅샷**: `python3 .superrelease/scripts/changed-packages.py --json`으로 scope별 anchor(그 scope 태그 포맷의 마지막 태그 = 마지막 릴리스 버전)를 수집한다 — 스크립트가 scope마다 자기 마지막 태그를 내부적으로 해석한다(positional ref 아님). tagless scope(anchor가 sha)는 `version.py get --scope <name>`으로 파일 버전을 폴백하되, 개발 수식어(-SNAPSHOT·-dev 등)가 붙은 버전은 "미릴리스 개발 버전"으로 표시한다. 스냅샷은 (패키지, 버전) 표로 정리한다.
- **§5 통합 노트**: 생성된 release-notes 스킬 절차로, 각 scope의 `anchor..HEAD` 커밋{{#if repo.mergePolicy == "squash"}}(squash 레포이므로 커밋 제목의 `(#N)`으로 PR 역참조){{/if}}을 취합해 train 통합 노트 초안을 쓰고 `.superrelease/templates/notes-train.md` 골격(스냅샷 표 + 하이라이트 + 주요 변경 + Breaking Changes rollup)으로 작성한다.
- **§6 dry-run 프리뷰 → 커밋/PR**: 스냅샷 표·다음 train 버전·생성 태그명·실행 명령·노트 미리보기를 보여주고 확인받는다. {{#if repo.releasePath == "direct-push"}}확인 후 notes-train.md를 커밋하고 `git push origin {{repo.defaultBranch}}`.{{else}}확인 후 **릴리스 PR 경로**: `release/train-<버전>` 브랜치에 notes-train 커밋을 쌓고 push → PR 1건 생성(`gh pr create --base {{repo.defaultBranch}}`; gh 미가용이면 GitHub MCP 폴백) → **중단**(태그는 머지 후). 머지 후 재개: §1의 mid-release/중단 감지가 잡거나, 사용자가 다시 호출하면 §7부터 이어간다.{{/if}}
- **§7 train 태그**{{#if github.release}} + GitHub Release{{/if}}: push 직전 충돌 재확인(`git ls-remote --tags origin train-<버전>`가 비어 있어야 함 — 있으면 즉시 중단). 태그 생성: `train.tag.signed`면 `git tag -s`, 아니고 `train.tag.annotated`면 `git tag -a`, 둘 다 아니면 `git tag`. annotated/signed면 `-F <통합 노트 파일>`로 노트 전문을 태그 메시지에 넣을 수 있다. → `git push origin train-<버전>`.{{#if github.release}} gh 경로: `gh release create train-<버전> --title "train-<버전>" --notes-file <노트 파일>`.{{/if}}
- **§8 실패 시**: 어디까지 진행됐는지(노트 커밋 / PR / 태그 / Release) 명시. **push된 태그는 되돌리지 않는다** — 잘못 나간 train은 다음 train으로 덮는다.

**불변**: train은 패키지 버전 파일을 수정하지 않는다(스냅샷은 읽기 전용). 버전 파일 bump·패키지 태그는 이 스킬의 소관이 아니다(release 스킬).

## E. `notes-train.md` 템플릿 (신규, 3번째 노트 템플릿)

`notes-single`·`notes-package`와 동형으로 `{{#unless scope.notes.language == "en"}}` / `{{#unless scope.notes.language == "ko"}}` ko/en 조건 블록을 가진다(대표 scope의 언어로 헤딩 고정). `preserve: "template"`.

섹션 구성:
- **포함 버전 스냅샷** — (패키지 | 버전) 표. train이 고정하는 조합.
- **하이라이트** — 이 train에서 가장 중요한 변경 1~3개.
- **주요 변경** — 패키지 전반의 사용자 관점 변경 요약.
- **Breaking Changes** — 포함 패키지들의 breaking rollup(없으면 삭제). 있으면 마이그레이션 가이드.

## F. init 번들 변경

- **번들 1 (성격·전략)**: "이중(루트 train + 패키지 개별)" 선택의 "M3 예정" 표시를 해제한다. 선택 시 → `monorepoStrategy: "independent"` 설정(independent scope 확정 흐름 동일) + `train` 객체 생성.
- **번들 2 (체계·SSOT·태그)**: train 루트 CalVer 패턴을 묻는다(기본 `YYYY.MICRO`, references 근거) + train 태그 포맷(기본 `train-{version}`, 패키지 `{pkg}@{ver}`와 별도 네임스페이스). train 태그 annotated 기본 yes.
- **config 템플릿**: `repo.train` 줄 제거, `train` 객체 추가. 각주(train 객체 필드 설명)·지원 범위 목록 갱신(release-train 지원 표시).

## G. references 정합

- `monorepo.md`: 이중 체계 절의 "M3로 미뤄진다" → 실동작 서술로 교체(train 객체·file-less·스냅샷=마지막 태그·전 패키지·CalVer 어휘 한계·direct-push/release-pr 양쪽 지원·train 태그 네임스페이스 `train-{version}`).
- `version-schemes.md`: CalVer 절에 train CalVer 어휘 한계(Spring Cloud 3파트 불가, `YYYY.MICRO` 권장)를 명시. "release train 루트 → CalVer 기본" 문구는 유지.

## H. 골든·테스트

- 신규 1트리 **`train-monorepo`**: `monorepoStrategy: "independent"` + `train` 객체 + 패키지 scope 2개 config. 생성된 `release-train` 스킬·`notes-train` 템플릿(및 release-monorepo·release-notes·나머지 툴킷)을 스냅샷으로 고정한다.
- 기존 11골든: `train` 객체 부재 → `train.enabled` falsy → release-train·notes-train 미생성 → **바이트 불변**.
- render 검증 3규칙 단위 테스트(train+비independent 거부 / 비calver 거부 / pattern·tag.format 누락 거부 + 유효 통과) + release-train 스킬 렌더 스모크(direct-push·release-pr 양쪽 조건 블록 확인).

## 제약·검증

- 동결 template dialect, 생성 SKILL.md ≤150줄, init SKILL.md ≤500줄.
- render 엔진·스크립트 산술·조작 **무변경** — 유일한 Python 변경은 `validate_config` 규칙 3건. next-version.py의 순수 calver 모드(`--current` 생략 시 MICRO=0 포함)와 changed-packages.py `--json` anchor를 그대로 재사용한다.
- 자립성: 생성 release-train 스킬은 `.superrelease/`·`.claude/` 상대 경로만 참조(release-notes 스킬·notes-train 템플릿을 프로즈로 참조 — 생성 스킬 간 참조 허용). 플러그인 경로 참조 금지.
- Python 3.9+ stdlib, exit 0/1/2, 코드·메시지 영어·생성 문서 한국어.
- TDD. 전체 스위트 + `claude plugin validate . --strict` + 골든 범위 확인.

## 비범위 (후속)

- train 버전 파일(BOM, 예: `spring-cloud-dependencies` pom.xml) — v1은 file-less 태그 파생.
- `train.includes` 부분집합 — v1은 전 패키지 scope.
- 모노레포 backfill(패키지 태그 네임스페이스 순회) 및 train 이력 backfill → M3c-3b / 후속.
- Spring Cloud식 3파트 CalVer(`YYYY.MINOR.MICRO`), headver train, sequential.
- train 태그가 moving major tag·CI 배포 트리거를 다루는 것(패키지 릴리스 소관).

## 예상 태스크 (writing-plans에서 확정)

1. render.py train 검증 규칙 3건 (TDD).
2. `release-train` 스킬 신규 + `notes-train` 템플릿 + manifest 엔트리 2건 + config 스키마 `train` 객체 (렌더 스모크 테스트).
3. init 번들 1·2 해제 + config 템플릿(`repo.train`→`train` 객체) + monorepo.md·version-schemes.md 정합.
4. 골든 `train-monorepo` 신규 + 최종 검증.
