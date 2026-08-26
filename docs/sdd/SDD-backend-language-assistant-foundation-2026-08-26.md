---
type: sdd
status: accepted
platform: backend
date: 2026-08-26
adr: ../adr/ADR-language-assistant-domain-model-2026-08-26.md
prd: ../superpowers/specs/2026-08-26-domain-model-v0.1-design.md
ux: []
lbs: []
related_sdd: []
phases:
  - id: P1
    title: Доменная модель и основа хранения
  - id: P2
    title: Неизменяемые свидетельства и проекции ученика
  - id: P3
    title: Граница учебной программы и выбор следующего действия
  - id: P4
    title: Теневая интеграция с текущей моделью
contracts:
  - id: DTO-01
    kind: value_object
    role: owner
    defined_in: P1.T1
  - id: EVENT-01
    kind: domain_event
    role: owner
    defined_in: P2.T2
open_questions: []
---

# SDD-backend: Основа языкового ассистента

> **Статус:** Accepted

- ADR: [`../adr/ADR-language-assistant-domain-model-2026-08-26.md`](../adr/ADR-language-assistant-domain-model-2026-08-26.md)
- PRD: [`../superpowers/specs/2026-08-26-domain-model-v0.1-design.md`](../superpowers/specs/2026-08-26-domain-model-v0.1-design.md)
- UX: нет; frontend и UI не входят в этот SDD
- LBS: нет; основа создаётся рядом с текущей моделью, без переключения существующих потребителей
- Progress: [`../progress/PROGRESS.md`](../progress/PROGRESS.md)

## 1. Обзор

SDD создаёт серверную основу для четырёх утверждённых ограниченных контекстов, не меняя существующие
публичные API и пользовательские сценарии. Новая модель сначала работает во внутреннем теневом
режиме: получает стабильные идентификаторы контента и целей, сохраняет события обучения, строит
проекции ученика и выбирает следующее действие через детерминированные политики.

Архитектурный стиль: чистые доменные модули, SQLAlchemy-маппинги хранения и прикладные сервисы.
Доменные модули не импортируют FastAPI или SQLAlchemy. Существующий способ передачи `Session` в
сервисы сохраняется; новый DI-фреймворк и отдельная абстракция unit of work не вводятся.

**Затронутые модули:**

- `backend/app/domain/` — новые агрегаты, объекты-значения, политики и порты;
- `backend/app/domain_models.py` — ORM-маппинги новой модели;
- `backend/app/repositories/domain.py` — операции хранения и контроль владения строками;
- `backend/app/services/` — начальная загрузка, запись событий, проекции, выбор и теневые адаптеры;
- `backend/alembic/` — создание схемы и обратимая миграция;
- `backend/tests/` — доменные, миграционные, интеграционные и конкурентные тесты, тесты replay.

**Существующий flow:**

- профиль создаётся и читается через `profile_service.py`;
- `learning_service.py` выбирает новые элементы и повторение, затем напрямую меняет
  `UserWordProgress`;
- `quiz_service.py` создаёт план теста, записывает `QuizAnswer` и в той же транзакции меняет прогресс;
- `models.py` и `schemas.py` являются общими плоскими модулями;
- Alembic импортирует `app.models`, а тестовые фикстуры создают `Base.metadata` в SQLite.

**Точки встраивания:**

- новые ORM-маппинги регистрируются в Alembic и тестовых метаданных без преобразования `app.models`
  в пакет;
- связь с текущей моделью опирается на `VocabularyItem.id` и `UserProfile.user_id`;
- теневые события добавляются до существующего `commit`, чтобы текущее изменение и свидетельство
  были атомарны;
- публичные схемы ответов и маршруты остаются неизменными.

## Errata vs ADR

| ADR-ref | В ADR | В SDD | Почему расхождение |
|---|---|---|---|
| §3, Learner Progress | State появляется только после evidence | Допускается явно помеченный `legacy_bootstrap` без synthetic events | Это уже требуется §3 Migration policy; SDD делает исключение исполнимым |
| §8, AI data flow | AI adapter показан только возле Practice | Candidate port подключён к selector, evaluator port — к Practice | Исправление направления зависимости без изменения AI boundary |
| §3, Practice & History | Retry lifecycle не уточнён | Каждый retry является новым связанным `ActivityInstance` | Сохраняет инвариант «один activity — один принятый event» при текущих quiz repeats |
| §3, Practice & History | `Submission` назван owned entity | В MVP это bounded `ResponseSubmission` value object команды | У него нет отдельной identity/lifecycle или persisted table; принятый результат атомарно становится event |
| §6, Risk 7 | Data lifecycle обязателен до free-form input | Production shadow history также gated этим решением | Даже bounded answer и learner ID уже являются learner data |

## 2. Реестр идентификаторов

| ID | Тип | Определён | NORMATIVE? |
|---|---|---|---|
| DTO-01 | value object | [P1.T1] § «Канонический блок: DTO-01» | да |
| SQL-01 | schema | [P1.T2] § «Канонический блок: SQL-01» | да |
| ALG-01 | algorithm | [P1.T1] § «Канонический блок: ALG-01» | да |
| EVENT-01 | domain event | [P2.T2] § «Канонический блок: EVENT-01» | да |
| ALG-02 | algorithm | [P2.T3] § «Канонический блок: ALG-02» | да |
| ALG-03 | algorithm | [P3.T2] § «Канонический блок: ALG-03» | да |
| ALG-04 | algorithm | [P3.T2] § «Канонический блок: ALG-04» | да |

## 3. План реализации

### Сводная таблица

| Фаза | ID | Название | Результат |
|---|---|---|---|
| 1 | P1 | [Доменная модель и основа хранения](SDD-backend-language-assistant-foundation-2026-08-26.P1.md) | Стабильные идентификаторы каталога и целей, новая схема рядом с текущей моделью |
| 2 | P2 | [Неизменяемые свидетельства и проекции ученика](SDD-backend-language-assistant-foundation-2026-08-26.P2.md) | Идемпотентные события и low-confidence baseline дают replay-состояние на уровне цели |
| 3 | P3 | [Граница учебной программы и выбор действия](SDD-backend-language-assistant-foundation-2026-08-26.P3.md) | Валидированный pilot A1 и детерминированный выбор работают только внутри backend |
| 4 | P4 | [Теневая интеграция с текущей моделью](SDD-backend-language-assistant-foundation-2026-08-26.P4.md) | Текущие new/review/quiz-сценарии дублируют свидетельства под feature flag без изменения API |

Фазы выполняются последовательно. P1 создаёт схему и доменную основу для остальных. P2 должна быть
завершена до P3, потому что селектор читает проекции ученика. P4 включается только после прохождения
миграционных, replay- и конкурентных тестов P1–P3 на PostgreSQL.

## 4. Архитектурный поток

```mermaid
flowchart TB
    Legacy["Legacy learning and quiz services"]
    Flag["Shadow feature flag"]
    Recorder["Learning event service"]
    Events["Immutable learning events"]
    Projector["Learner state projector"]
    State["Learner target states"]
    Curriculum["Published curriculum"]
    Selector["Next activity service"]
    Catalog["Language catalog"]
    AiCandidate["Optional candidate port"]
    AiEvaluator["Optional evaluator port"]

    Legacy --> Flag
    Flag -->|"enabled"| Recorder
    Recorder --> Events
    Events --> Projector
    Projector --> State
    Curriculum --> Selector
    State --> Selector
    Catalog --> Selector
    AiCandidate -.-> Selector
    AiEvaluator -.-> Recorder
```

## 5. Глоссарий путей

```text
backend/app/config.py                                      (~)
backend/app/db.py                                          (~)
backend/app/domain/__init__.py                             (+)
backend/app/domain/catalog.py                              (+)
backend/app/domain/curriculum.py                           (+)
backend/app/domain/policies.py                             (+)
backend/app/domain/ports.py                                (+)
backend/app/domain/practice.py                             (+)
backend/app/domain/progress.py                             (+)
backend/app/domain/target.py                               (+)
backend/app/domain_models.py                               (+)
backend/app/repositories/__init__.py                       (+)
backend/app/repositories/domain.py                         (+)
backend/app/services/curriculum_service.py                 (+)
backend/app/services/domain_bootstrap_service.py           (+)
backend/app/services/domain_shadow_service.py              (+)
backend/app/services/learning_event_service.py             (+)
backend/app/services/learner_projection_service.py         (+)
backend/app/services/legacy_progress_bootstrap_service.py  (+)
backend/app/services/learning_service.py                    (~)
backend/app/services/next_activity_service.py              (+)
backend/app/services/practice_service.py                   (+)
backend/app/services/quiz_service.py                        (~)
backend/app/seed.py                                         (~)
backend/alembic/env.py                                      (~)
backend/alembic/versions/20260826_0005_domain_foundation.py (+)
backend/tests/conftest.py                                   (~)
backend/tests/test_curriculum.py                            (+)
backend/tests/test_domain_catalog.py                        (+)
backend/tests/test_domain_shadow.py                         (+)
backend/tests/test_learning_events.py                       (+)
backend/tests/test_legacy_progress_bootstrap.py             (+)
backend/tests/test_learning.py                              (~)
backend/tests/test_migrations.py                            (~)
backend/tests/test_next_activity.py                         (+)
backend/tests/test_projection.py                            (+)
backend/tests/test_quizzes.py                               (~)
docs/product-state.md                                       (~)
docs/progress/PROGRESS.md                                   (~)
```

## 6. Открытые вопросы

Открытых вопросов, блокирующих реализацию P1–P3 и выключенного P4, нет. Production-включение shadow,
identity/access, переключение UI, промышленный AI-оценщик, политика жизненного цикла learning
history и паритет с текущим поведением относятся к следующим SDD и записаны в
`docs/progress/PROGRESS.md`.
