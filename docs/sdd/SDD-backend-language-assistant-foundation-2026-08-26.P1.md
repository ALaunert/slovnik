# SDD-backend, фаза P1: доменная модель и основа хранения

- Родительский документ: [`SDD-backend-language-assistant-foundation-2026-08-26.md`](SDD-backend-language-assistant-foundation-2026-08-26.md)
- **ID:** P1
- **Цель:** создать чистые доменные типы, стабильные идентификаторы, ORM-маппинги и обратимую схему
  рядом с текущими таблицами.
- **Зависимости:** нет.
- **Команда для реализации:** выполнить P1.T1–P1.T4 по порядку, не подключая новую модель к
  публичным маршрутам и не меняя текущее поведение.

## Текущее поведение

Фаза не заменяет текущий поток. `VocabularyItem`, `UserProfile`, `UserWordProgress`, `QuizAttempt` и
`QuizAnswer` продолжают работать без изменения схемы или API. Новые таблицы добавляют только внешние
ключи и ссылки на существующие идентификаторы.

## Задачи

#### [P1.T1] Зафиксировать доменные типы и канонический TargetSpec

**Уровень:** Complex

**Файлы:**

```changeset
+ backend/app/domain/__init__.py
+ backend/app/domain/catalog.py
+ backend/app/domain/curriculum.py
+ backend/app/domain/practice.py
+ backend/app/domain/progress.py
+ backend/app/domain/target.py
+ backend/app/domain/ports.py
```

**Референсы:**

- `docs/superpowers/specs/2026-08-26-domain-model-v0.1-design.md`
- `backend/app/schemas.py` — стиль валидации enum и значений, но без зависимости домена от Pydantic
- `backend/app/services/learning_service.py` — текущая семантика оценки и срока, но не источник истины для
  новой модели

**Что сделать:**

Создать неизменяемые объекты-значения и типы состояния агрегатов без импортов из FastAPI, SQLAlchemy
или OpenAI SDK. `TargetSpec` является единственным каноническим способом адресовать знание ученика.
Доменные enum сериализуются стабильными строчными значениями wire-формата. Идентификатор
опубликованного контента не переиспользуется после вывода из обращения.

**Ключевые ограничения:**

- доменный слой зависит только от стандартной библиотеки Python;
- у одного действия MVP одна основная `TargetSpec`;
- `Form` поддерживает поверхностные реализации слов и MWE;
- неизвестные и добавочные поля JSON не становятся частью доменного равенства;
- стабильные ID создаются прикладным слоем как строчные строки UUID.

##### Канонический блок: DTO-01 (DTO) (NORMATIVE)

> NORMATIVE. Эта таблица является источником истины для канонического `TargetSpec` v1.

| Поле | Тип | Wire value / правило | Описание |
|---|---|---|---|
| `schema_version` | integer | `1` | Версия канонической сериализации |
| `target_kind` | enum | `sense`, `form`, `construction` | Тип стабильного идентификатора цели |
| `target_id` | UUID string | канонический строчный UUID | ID агрегата или сущности цели |
| `capability` | enum | `recognize_meaning`, `retrieve_form`, `apply_construction` | Измеряемая способность |
| `modality` | enum | `written` | Модальность свидетельства |
| `condition` | object | канонический JSON, по умолчанию `{}` | Разреженное морфосинтаксическое условие |
| `target_key` | string | результат ALG-01 | Объект-значение для хранения и индексации |

##### Канонический блок: ALG-01 (ALG) (NORMATIVE)

> NORMATIVE. Алгоритм определяет единственный способ построения `target_key` v1.

```text
validate TargetSpec fields against DTO-01
canonical_condition = JSON(condition, sorted keys, NFC strings, no whitespace)
condition_hash = SHA256(canonical_condition as UTF-8).hexdigest()
target_key = join with ':'
    'v1'
    target_kind
    lowercase target_id
    capability
    modality
    condition_hash
reject target_key longer than 255 characters
```

**Проверка:**

- модульные тесты доказывают детерминированность ключа при другом порядке JSON-полей и
  NFC-эквивалентных строках;
- невалидные enum, UUID и condition отклоняются до сохранения;
- доменные модули импортируются без инициализации настроек приложения и базы.

---

#### [P1.T2] Добавить ORM-маппинги и обратимую схему

**Уровень:** Complex

**Файлы:**

```changeset
+ backend/app/domain_models.py
~ backend/app/db.py
~ backend/alembic/env.py
+ backend/alembic/versions/20260826_0005_domain_foundation.py
~ backend/tests/conftest.py
~ backend/tests/test_migrations.py
```

**Референсы:**

- `backend/app/models.py` — типизированные маппинги SQLAlchemy 2 и общий `Base`
- `backend/alembic/versions/20260702_0001_initial_schema.py` — стиль начальных таблиц и ограничений
- `backend/alembic/versions/20260725_0004_active_recall_schedule.py` — последняя ревизия и понижение
- `backend/tests/test_migrations.py` — проверка полного цикла SQLite/PostgreSQL

**Что сделать:**

Добавить ORM-маппинги в отдельный модуль и импортировать их в метаданные времени выполнения, тестов
и Alembic. Одна миграция создаёт основную схему; понижение удаляет только новые таблицы и индексы в
обратном порядке зависимостей. Существующие таблицы и данные не меняются.

**Ключевые ограничения:**

- PostgreSQL — промышленная цель, SQLite — цель тестовой совместимости; MySQL не поддерживается;
- строки UUID генерируются прикладным слоем, значения базы по умолчанию не расходятся между диалектами;
- поля JSON используют переносимый тип SQLAlchemy `JSON`, а не специфичный для PostgreSQL `JSONB`;
- полиморфный `target_id` проверяется прикладным слоем, потому что один внешний ключ не может
  ссылаться на три таблицы целей;
- таблицы ученика имеют внешний ключ на существующий `user_profiles.user_id`;
- свободный текст беседы не входит в схему.

##### Канонический блок: SQL-01 (SQL) (NORMATIVE)

> NORMATIVE. DDL ниже задаёт результирующую схему для PostgreSQL и SQLite; миграция Alembic выражает
> тот же контракт через переносимые операции SQLAlchemy. MySQL не является целевым диалектом проекта,
> поэтому отдельный MySQL DDL намеренно не входит в этот SDD.

```sql
CREATE TABLE language_lexical_units (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('word', 'mwe')),
    legacy_vocabulary_item_id BIGINT UNIQUE,
    status TEXT NOT NULL CHECK (status IN ('draft', 'published', 'retired')),
    revision INTEGER NOT NULL CHECK (revision >= 1),
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    FOREIGN KEY (legacy_vocabulary_item_id) REFERENCES vocabulary_items(id)
);

CREATE TABLE language_senses (
    id TEXT PRIMARY KEY,
    lexical_unit_id TEXT NOT NULL,
    glosses JSON NOT NULL,
    notes TEXT,
    examples JSON NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('draft', 'published', 'retired')),
    revision INTEGER NOT NULL CHECK (revision >= 1),
    FOREIGN KEY (lexical_unit_id) REFERENCES language_lexical_units(id)
);

CREATE TABLE language_forms (
    id TEXT PRIMARY KEY,
    lexical_unit_id TEXT NOT NULL,
    form_kind TEXT NOT NULL CHECK (form_kind IN ('citation', 'inflected', 'fixed')),
    orthographies JSON NOT NULL,
    morph_features JSON NOT NULL,
    stress_pattern JSON,
    status TEXT NOT NULL CHECK (status IN ('draft', 'published', 'retired')),
    revision INTEGER NOT NULL CHECK (revision >= 1),
    FOREIGN KEY (lexical_unit_id) REFERENCES language_lexical_units(id)
);

CREATE TABLE language_constructions (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    morph_features JSON NOT NULL,
    examples JSON NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('draft', 'published', 'retired')),
    revision INTEGER NOT NULL CHECK (revision >= 1)
);

CREATE TABLE curriculum_versions (
    id TEXT PRIMARY KEY,
    curriculum_code TEXT NOT NULL,
    version_number INTEGER NOT NULL CHECK (version_number >= 1),
    cefr_level TEXT NOT NULL CHECK (cefr_level IN ('A1', 'A2', 'B1', 'B2', 'C1', 'C2')),
    status TEXT NOT NULL CHECK (status IN ('draft', 'active', 'retired')),
    created_at TIMESTAMP NOT NULL,
    published_at TIMESTAMP,
    retired_at TIMESTAMP,
    UNIQUE (curriculum_code, version_number)
);

CREATE TABLE curriculum_nodes (
    id TEXT PRIMARY KEY,
    curriculum_version_id TEXT NOT NULL,
    target_key TEXT NOT NULL,
    target_kind TEXT NOT NULL CHECK (target_kind IN ('sense', 'form', 'construction')),
    target_id TEXT NOT NULL,
    capability TEXT NOT NULL CHECK (capability IN ('recognize_meaning', 'retrieve_form', 'apply_construction')),
    modality TEXT NOT NULL CHECK (modality IN ('written')),
    condition_payload JSON NOT NULL,
    priority INTEGER NOT NULL,
    outcome_code TEXT NOT NULL,
    FOREIGN KEY (curriculum_version_id) REFERENCES curriculum_versions(id),
    UNIQUE (curriculum_version_id, target_key)
);

CREATE TABLE curriculum_prerequisites (
    id TEXT PRIMARY KEY,
    curriculum_version_id TEXT NOT NULL,
    prerequisite_node_id TEXT NOT NULL,
    dependent_node_id TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('hard', 'soft')),
    FOREIGN KEY (curriculum_version_id) REFERENCES curriculum_versions(id),
    FOREIGN KEY (prerequisite_node_id) REFERENCES curriculum_nodes(id),
    FOREIGN KEY (dependent_node_id) REFERENCES curriculum_nodes(id),
    UNIQUE (curriculum_version_id, prerequisite_node_id, dependent_node_id, kind)
);

CREATE TABLE practice_runs (
    id TEXT PRIMARY KEY,
    learner_id TEXT NOT NULL,
    curriculum_version_id TEXT,
    legacy_quiz_attempt_id BIGINT UNIQUE,
    status TEXT NOT NULL CHECK (status IN ('active', 'completed', 'abandoned')),
    selection_policy_version TEXT NOT NULL,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    FOREIGN KEY (learner_id) REFERENCES user_profiles(user_id),
    FOREIGN KEY (curriculum_version_id) REFERENCES curriculum_versions(id),
    FOREIGN KEY (legacy_quiz_attempt_id) REFERENCES quiz_attempts(id)
);

CREATE TABLE activity_instances (
    id TEXT PRIMARY KEY,
    practice_run_id TEXT NOT NULL,
    target_key TEXT NOT NULL,
    learning_intent TEXT NOT NULL CHECK (learning_intent IN ('acquire', 'review', 'strengthen', 'assess')),
    operation TEXT NOT NULL CHECK (operation IN ('recognize', 'retrieve', 'complete', 'transform')),
    spec_payload JSON NOT NULL,
    generator_kind TEXT NOT NULL CHECK (generator_kind IN ('curated', 'model_assisted')),
    generator_version TEXT NOT NULL,
    scorer_kind TEXT NOT NULL CHECK (scorer_kind IN ('deterministic', 'self_report', 'model_assisted')),
    scorer_version TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'completed', 'cancelled')),
    selected_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    FOREIGN KEY (practice_run_id) REFERENCES practice_runs(id)
);

CREATE TABLE learning_events (
    id TEXT PRIMARY KEY,
    schema_version INTEGER NOT NULL CHECK (schema_version >= 1),
    learner_id TEXT NOT NULL,
    practice_run_id TEXT NOT NULL,
    activity_instance_id TEXT NOT NULL,
    target_key TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK (event_type IN ('exposure', 'response_evaluated')),
    observation_payload JSON NOT NULL,
    idempotency_key TEXT NOT NULL,
    occurred_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL,
    FOREIGN KEY (learner_id) REFERENCES user_profiles(user_id),
    FOREIGN KEY (practice_run_id) REFERENCES practice_runs(id),
    FOREIGN KEY (activity_instance_id) REFERENCES activity_instances(id),
    UNIQUE (learner_id, idempotency_key)
);

CREATE TABLE learner_target_states (
    id TEXT PRIMARY KEY,
    learner_id TEXT NOT NULL,
    target_key TEXT NOT NULL,
    competence_success_weight DOUBLE PRECISION NOT NULL CHECK (competence_success_weight >= 0),
    competence_failure_weight DOUBLE PRECISION NOT NULL CHECK (competence_failure_weight >= 0),
    uncertainty DOUBLE PRECISION NOT NULL CHECK (uncertainty >= 0 AND uncertainty <= 1),
    evidence_count INTEGER NOT NULL CHECK (evidence_count >= 0),
    last_evidence_at TIMESTAMP,
    memory_due_at TIMESTAMP,
    memory_interval_days INTEGER NOT NULL CHECK (memory_interval_days >= 0),
    memory_lapses INTEGER NOT NULL CHECK (memory_lapses >= 0),
    memory_policy_version TEXT NOT NULL,
    projection_policy_version TEXT NOT NULL,
    source_kind TEXT NOT NULL CHECK (source_kind IN ('native_event', 'legacy_bootstrap')),
    updated_at TIMESTAMP NOT NULL,
    FOREIGN KEY (learner_id) REFERENCES user_profiles(user_id),
    UNIQUE (learner_id, target_key)
);

CREATE INDEX ix_language_senses_lexical_unit ON language_senses(lexical_unit_id);
CREATE INDEX ix_language_forms_lexical_unit ON language_forms(lexical_unit_id);
CREATE INDEX ix_curriculum_nodes_target ON curriculum_nodes(target_key);
CREATE INDEX ix_practice_runs_learner_status ON practice_runs(learner_id, status);
CREATE INDEX ix_learning_events_learner_time ON learning_events(learner_id, occurred_at);
CREATE INDEX ix_learning_events_target_time ON learning_events(target_key, occurred_at);
CREATE INDEX ix_learner_target_states_due ON learner_target_states(learner_id, memory_due_at);
```

**Проверка:**

- полный цикл миграции проходит на временной SQLite и одноразовой PostgreSQL;
- повышение с ревизии `20260725_0004` побайтово сохраняет проверяемые поля текущих строк;
- понижение удаляет только 11 новых таблиц и их индексы;
- `Base.metadata.create_all` видит текущие и доменные маппинги.

---

#### [P1.T3] Реализовать репозитории и начальную загрузку текущего контента

**Уровень:** Standard

**Файлы:**

```changeset
+ backend/app/repositories/__init__.py
+ backend/app/repositories/domain.py
+ backend/app/services/domain_bootstrap_service.py
~ backend/app/seed.py
```

**Референсы:**

- `backend/app/services/vocabulary_service.py` — текущий способ работы с `Session` и запросами
- `backend/app/seed.py` — текущая точка входа детерминированных начальных данных
- `backend/app/models.py` — исходные сущности текущей модели

**Что сделать:**

Модуль репозитория реализует узкие операции по владению агрегатами, не возвращая ORM-объекты в
доменные политики. Начальная загрузка идемпотентно сопоставляет каждый подходящий `VocabularyItem`
с одной лексической единицей, одним смыслом по умолчанию и одной словарной или фиксированной формой.
Текущие CEFR и тема сохраняются как метаданные загрузки для P3, а не истина контента.

**Ключевые ограничения:**

- повторная загрузка не создаёт новые стабильные ID для уже сопоставленного словарного элемента;
- автоопределение WORD/MWE консервативно: неоднозначная запись остаётся WORD и помечается для редактора;
- структурированное ударение переносится без вывода; текущий текстовый маркер остаётся резервной аннотацией;
- примеры сохраняются как неразобранная текущая нагрузка;
- загрузка не создаёт синтетические события обучения.

**Проверка:**

- интеграционные тесты доказывают идемпотентность и стабильность сопоставлений;
- кириллические и латинские формы и существующее ударение сохраняются после записи и чтения;
- невалидный или частичный текущий контент не публикуется автоматически.

---

#### [P1.T4] Покрыть тестами доменную основу и схему

**Уровень:** Standard

**Файлы:**

```changeset
+ backend/tests/test_domain_catalog.py
~ backend/tests/test_migrations.py
```

**Референсы:**

- `backend/tests/test_schema.py`
- `backend/tests/test_migrations.py`

**Что сделать:**

Добавить сфокусированные модульные и интеграционные тесты инвариантов агрегатов, канонизации
TargetSpec, начального сопоставления и сохранности миграции. Не дублировать сквозные текущие тесты.

**Ключевые ограничения:**

- тестовые фикстуры импортируют новые маппинги до `Base.metadata.create_all`;
- цель PostgreSQL не пропускает ошибки переданной конфигурации;
- междиалектные проверки сравнивают семантическую схему, а не представление типов диалекта.

**Проверка:**

- `ruff check .`;
- целевые доменные и миграционные тесты на SQLite;
- полный цикл миграции PostgreSQL с `SLOVNIK_TEST_POSTGRES_ADMIN_URL`.

## Проверка фазы

**Автотесты:** доменные модульные тесты, интеграционные тесты репозитория и начальной загрузки,
полный цикл миграции SQLite и PostgreSQL.

**Откат:** понизить ревизию `20260826_0005`; текущие таблицы и API остаются без изменений.
