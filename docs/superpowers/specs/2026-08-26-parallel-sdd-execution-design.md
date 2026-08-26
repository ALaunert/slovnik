# Parallel Execution Design for Language Assistant SDD

> **Статус:** Approved; reflected in SDD revision 2

- Дата: 2026-08-26
- SDD: [`../../sdd/SDD-backend-language-assistant-foundation-2026-08-26.md`](../../sdd/SDD-backend-language-assistant-foundation-2026-08-26.md)
- Readiness review: [`../../progress/parallel-sdd-readiness-2026-08-26.md`](../../progress/parallel-sdd-readiness-2026-08-26.md)
- Scope: подготовка backend foundation SDD к работе трёх независимых implementation workstreams и
  одного интегратора
- Production code/UI: не входят в этот документ

## 1. Цель

Сделать план исполнимым параллельно без параллельного редактирования одних файлов, скрытых
межкомандных зависимостей и преждевременного merge незавершённых contracts. Семантика Domain Model,
ADR, DTO-01, EVENT-01, SQL-01 и ALG-01–04 не меняется.

## 2. Оценка исходного SDD

Исходная готовность к параллельной разработке: **4/10**.

| Критерий | Было | Основная проблема |
|---|---:|---|
| Независимое file ownership | 2/10 | `repositories/domain.py`, `domain/policies.py`, `domain/ports.py` и shadow service были общими hotspots |
| Явный dependency graph | 5/10 | Фазы были полностью последовательными, хотя pure-domain работу можно вести через frozen contracts |
| Изолированные тесты | 4/10 | Несколько задач одновременно меняли одни test-файлы |
| Integration gates | 5/10 | Phase checks существовали, но merge eligibility и contract freeze не были определены |
| Rollback/diagnostics | 6/10 | Откат фаз описан, но ответственность интегратора и конфликтный протокол отсутствовали |

Целевая готовность после ревизии: **8/10**. Оставшиеся два пункта зависят не от документа, а от
реального соблюдения ownership, качества branch isolation и скорости contract review.

## 3. Рассмотренные варианты

### 3.1. Контекстные workstreams + интегратор — выбран

- WS-A: Language Catalog + Curriculum.
- WS-B: Practice & History.
- WS-C: Learner Progress + Selection.
- Integrator: shared contracts, ORM registry, migration, cross-context tests и merge gates.

Преимущества: ownership совпадает с bounded contexts, большинство unit tests не требует чужой
реализации, а интеграционные зависимости проходят через frozen contracts.

### 3.2. Горизонтальные слои

Отдельные исполнители для domain, persistence и services. Вариант отклонён: каждый use case требует
последовательных handoff, а типы и ORM постоянно меняются разными владельцами.

### 3.3. Вертикальные legacy flows

Отдельные исполнители для new words, review и quiz. Вариант отклонён: до foundation он дублирует
target/event/projection logic и снова смешивает bounded contexts.

## 4. Execution topology

### Gate 0 — contract freeze

Integrator фиксирует DTO-01, EVENT-01, SQL-01, shared enums, stable serialization, package registry
и repository interfaces. После Gate 0 workstream не меняет shared contract напрямую: изменение
оформляется contract-change request с impact list и принимается интегратором.

### Wave 1 — context foundations

- Integrator готовит registry, migration shell и общие fixtures.
- WS-A реализует Catalog и Curriculum foundations.
- WS-B реализует Practice foundation.
- WS-C реализует Learner Progress foundation.

Wave завершается P1 integration gate: единая migration, metadata discovery, contract tests и
round-trip schema проходят после объединения всех context branches.

### Wave 2 — domain behavior

- WS-A: curriculum publication, frontier и technical A1 pilot.
- WS-B: run/activity lifecycle, immutable events и idempotency.
- WS-C: projector, memory policy, legacy baseline и selector через frozen curriculum/progress ports.

P3 selector разрешено разрабатывать с fakes параллельно P2, но интегрировать только после зелёного
projection contract gate. P2/P3 считаются завершёнными после общих replay, migration и selector
integration tests.

### Wave 3 — legacy shadow

Integrator фиксирует shadow contracts и feature flag. Затем learning adapter и quiz adapter
разрабатываются параллельно. Shadow comparison начинается после обоих adapter gates; полный backend
regression и документация принадлежат интегратору.

## 5. File ownership

| Owner | Exclusive paths while workstream is active |
|---|---|
| Integrator | `domain/shared.py`, `domain/target.py`, package `__init__`, ORM registry, Alembic migration, `db.py`, `alembic/env.py`, shared fixtures/contracts, progress docs |
| WS-A | catalog/curriculum domain, ORM and repositories; curriculum/bootstrap services; seed; their unit tests |
| WS-B | practice domain/ports/ORM/repository; practice/event/quiz-shadow services; their unit tests |
| WS-C | progress/memory/selection domain and ports; progress repository; projection/selection/learning-shadow services; their unit tests |

Один путь не принадлежит двум одновременно активным workstreams. Cross-context imports используют
public contracts; изменение чужого файла выполняет его owner либо integrator после gate merge.

## 6. Hotspot decomposition

- `domain_models.py` → context package `domain_models/{catalog,curriculum,practice,progress}.py` +
  integrator-owned registry.
- `repositories/domain.py` → четыре context repositories.
- `domain/policies.py` → `memory_policy.py`, `curriculum_policy.py`, `selection_policy.py`.
- `domain/ports.py` → `practice_ports.py`, `selection_ports.py`.
- `domain_shadow_service.py` → contracts, learning, quiz и comparison services.
- Общие shadow tests → contract, learning, quiz, comparison и final integration files.

## 7. Merge gates

| Gate | Merge разрешён, когда |
|---|---|
| G0 Contract | Canonical contracts frozen; ownership manifest и import rules проверены |
| G1 Foundation | Context unit tests green; ORM registry и migration round trip green на SQLite/PostgreSQL |
| G2 Evidence | Practice/event и projection tracks проходят idempotency, replay и concurrency matrix |
| G3 Selection | Curriculum publication и selector integration проходят на frozen projection fixtures |
| G4 Shadow | Flag-off regression green; learning/quiz adapters атомарны; comparison non-authoritative |

Незелёная ветка не мержится «для разблокировки» другого track. Integrator объединяет только
gate-ready commits и запускает общий quality gate после каждого merge.

## 8. Branch and conflict protocol

- Один worktree/branch на workstream; worktree располагается вне repository tree.
- Коммиты атомарны по SDD task slug.
- Shared contract меняется отдельным integrator commit до rebase зависимых branches.
- Workstream не разрешает semantic conflict выбором «ours/theirs»; конфликт возвращается owner.
- Generated migration принадлежит только integrator; параллельные Alembic revisions в этой wave
  запрещены.

## 9. Success criteria

1. Три workstreams после G0 могут работать без изменения одного tracked path.
2. У каждой task есть owner, входной contract, локальная проверка и merge gate.
3. P2/P3 pure-domain work допускает параллельную разработку, но integration сохраняет dependency
   projection-before-selection.
4. P4 learning и quiz adapters параллельны и не делят implementation/test files.
5. Один integrator владеет migration, registry, shared contracts и итоговой документацией.
