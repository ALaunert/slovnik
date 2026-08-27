# SDD-backend, фаза P4: теневая интеграция с текущей моделью

- Родительский документ: [`SDD-backend-language-assistant-foundation-2026-08-26.md`](SDD-backend-language-assistant-foundation-2026-08-26.md)
- **ID:** P4
- **Цель:** дублировать ограниченные свидетельства из текущих команд новых слов, повторения и тестов
  под выключенным по умолчанию feature flag, не меняя публичные API и ответы.
- **Зависимости:** G2/P2, G3/P3, EVENT-01, ALG-03.
- **Команда для реализации:** INT выполняет P4.T1, после чего WS-C/P4.T2 и WS-B/P4.T3 идут
  параллельно. P4.T4 следует после обоих adapters, INT закрывает P4.T5. Флаг остаётся выключенным по
  умолчанию; production enable запрещён до data-lifecycle и identity/access решений.

## Текущее поведение

> INFORMATIVE. Эта фаза добавляет только атомарные теневые побочные эффекты. Текущие выбор,
> оценивание, тела ответов, коды состояния, интервалы повторения, признаки слабых слов и правила
> повторной попытки в тесте остаются источником поведения времени выполнения.

- Завершение новых слов продолжает проверять ID по заново рассчитанному текущему выбору.
- Оценка повторения продолжает блокировать и перепроверять срок, используя текущие правила
  Again/Hard/Good/Easy.
- Ответ в тесте сохраняет максимум две попытки, текущий точный оценщик и изменение weak/schedule.
- Существующие схемы маршрутов и согласование состояния на frontend не меняются.
- Переключение чтения или удаление текущей логики требует отдельного LBS и миграционного SDD.

## Задачи

#### [P4.T1] Зафиксировать shadow contracts и feature flag

**Уровень:** Standard

**Файлы:**

```changeset
~ backend/app/config.py
+ backend/app/services/domain_shadow_contracts.py
+ backend/tests/test_domain_shadow_contracts.py
```

**Референсы:**

- EVENT-01 и ALG-02 в P2
- `backend/app/config.py` — способ валидации настроек и значений по умолчанию

**Что сделать:**

INT добавляет `LANGUAGE_ASSISTANT_SHADOW_ENABLED=false` и фиксирует typed contracts для legacy
source refs, idempotency keys, policy/reason codes, adapter results и non-authoritative comparison.
Файл не импортирует `learning_service.py` или `quiz_service.py` и становится frozen до G4.

**Ключевые ограничения:**

- adapters не меняют common contract напрямую;
- flag-off path не создаёт domain queries/rows;
- contract не содержит raw learner response или provider secrets;
- production enable gate кодируется отдельной config validation/policy, а не комментарием.

**Проверка:**

- contract tests фиксируют enum/wire values и flag default;
- learning/quiz adapter fakes импортируют один contract без взаимных imports;
- production-like config без обязательных gates отклоняется.

---

#### [P4.T2] Подключить learning shadow adapter

**Уровень:** Complex

**Файлы:**

```changeset
+ backend/app/services/shadow_learning_service.py
~ backend/app/services/learning_service.py
~ backend/tests/test_learning.py
+ backend/tests/test_learning_shadow.py
```

**Референсы:**

- `backend/app/services/learning_service.py` — точное текущее поведение транзакций и блокировок
- `backend/app/services/domain_shadow_contracts.py` — frozen adapter contract из P4.T1
- EVENT-01 и ALG-02 в P2

**Что сделать:**

WS-C подключает frozen contract к learning service. При выключенном флаге сохраняется наблюдаемое
поведение базы/API. При включённом пакет новых слов создаёт actions/events знакомства, а оценка
повторения — одно self-report retrieval event; всё выполняется до существующего `commit`.

Знакомство использует `activity_kind=exposure`, `operation=NULL` и основной
`Sense + retrieve_form` target, который подготавливает назначенное через день продуктивное review,
но не получает competence credit. Повторение использует тот же target; citation `Form` хранится в
снимке задания, а не становится отдельным progress target.
Selection metadata использует policy versions `legacy-new-word-v1`/`legacy-review-v1` и reason
codes `legacy_new_word`/`legacy_review`; эти значения описывают наблюдавшийся legacy choice, а не
решение нового selector.

Одна принятая команда `complete_new_words` создаёт один run со всеми exposure activities в порядке
входного списка и завершает его в той же транзакции. Одна принятая review rating создаёт и завершает
single-activity run. Если idempotency lookup находит ранее принятый event, новый run/activity не
создаётся.

Ключи идемпотентности для текущей модели:

- новое знакомство: стабильный кортеж ученика, строки прогресса и времени первого показа;
- повторение: строка прогресса, заблокированный срок до перехода и принятая оценка.

Теневой доменный сервис владеет сопоставлением текущего слова с основным лексическим `TargetSpec`.
Отсутствующее или неоднозначное сопоставление прерывает транзакцию при включённом флаге; молча
создавать цель запрещено.

**Ключевые ограничения:**

- ошибка теневой записи откатывает текущее изменение и событие вместе;
- выключенный флаг не выполняет новых запросов и записей;
- самостоятельно оценённое повторение не даёт competence credit, но меняет memory schedule через
  сохранённую Again/Hard/Good/Easy-семантику `memory-v1`;
- повтор/idempotency conflict не оставляет пустой новый run или activity;
- новый текст исключений не попадает в стабильные продуктовые ошибки 400; непредвиденные
  инфраструктурные сбои остаются ошибками 500 и журналируются без сырых ответов;
- публичные схемы и маршруты не меняются.

**Проверка:**

- регрессионные тесты при выключенном флаге подтверждают отсутствие доменных строк;
- завершение новых слов при включённом флаге создаёт по одному событию знакомства на принятое слово;
- повторение создаёт ровно одно событие при повторе после потери ответа и конкурентной оценке;
- Again/Hard/Good/Easy меняют только memory projection и не меняют competence weights;
- знакомство не меняет competence, но создаёт тот же первый review due через один день;
- искусственный сбой записи события не меняет текущий прогресс;
- существующее поведение из `test_learning.py` остаётся зелёным.

---

#### [P4.T3] Подключить quiz shadow adapter

**Уровень:** Complex

**Файлы:**

```changeset
~ backend/app/services/quiz_service.py
+ backend/app/services/shadow_quiz_service.py
~ backend/tests/test_quizzes.py
+ backend/tests/test_quiz_shadow.py
```

**Референсы:**

- `backend/app/services/quiz_service.py` — исходное поведение запуска, раскрытия, ответа и завершения
- `backend/app/models.py` — `QuizAttempt.question_plan` и `QuizAnswer`
- `backend/app/services/domain_shadow_contracts.py` — frozen adapter contract из P4.T1
- EVENT-01 в [P2.T2]

**Что сделать:**

WS-B при включённом теневом режиме создаёт для quiz один сопоставленный `PracticeRun` и по одному
`ActivityInstance` на запланированный вопрос, сохраняя точный снимок вопроса. Обработка ответа
выполняет `flush` для `QuizAnswer`, строит ключ идемпотентности
`legacy:quiz-answer:{quiz_answer_id}` и добавляет одно событие до существующего `commit`.
Самопроверка записывает `SELF_REPORT`, а выбор и ввод используют текущий детерминированный результат.
Исходные activities получают `sequence_number` из `question_plan`; retry добавляется в конец run.
Selection metadata использует `selection_policy_version=legacy-quiz-v1` и
`selection_reason=legacy_quiz`.

Перед проверкой history сервис блокирует `QuizAttempt` и соответствующий pending
`ActivityInstance`, затем перечитывает ответы. Неверный первый ответ завершает исходный activity и
создаёт новый retry activity; второй ответ относится к нему. Поэтому каждый accepted answer имеет
собственный activity/event, а конкурентные запросы не обходят лимит.

**Ключевые ограничения:**

- текущий изменяемый оценщик словаря остаётся источником поведения времени выполнения в P4;
- снимок действия сохраняет использованные при запуске формулировку, варианты и версию ответа;
- поведение повторов и лимита ответов не меняется;
- повторная попытка является новым связанным activity и событием со своим `QuizAnswer.id`;
- `sr_to_ru_choice` адресует `Sense + recognize_meaning`, `ru_to_sr_typing` —
  `Sense + retrieve_form`, self-check — self-report по `Sense + recognize_meaning`;
- self-check `forgot` маппится на memory rating `AGAIN`, `remembered` — на `GOOD`; оба остаются
  `evaluation_outcome=unknown` и не меняют competence; отличие `AGAIN +10m` от текущего quiz
  immediate-due поведения является ожидаемой shadow policy difference, а не изменением legacy flow;
- текущая итоговая оценка теста и обработка weak не меняются;
- успешный `complete_quiz` завершает связанный `PracticeRun` в той же транзакции; незавершённый
  legacy attempt не получает выдуманный abandonment;
- сырой prompt провайдера и неограниченный пользовательский текст не попадают в журналы.

**Проверка:**

- каждый принятый ответ создаёт ровно одно сопоставленное событие;
- неверный ответ и последующее исправление создают два события в хронологическом порядке;
- два конкурентных первых ответа сериализуются: один принимается, второй получает существующую
  стабильную ошибку лимита и не создаёт `QuizAnswer`/event;
- ответ другого пользователя, вне плана или после завершения не создаёт событие;
- завершение quiz атомарно завершает domain run только после completed state всех activities;
- искусственный сбой теневой записи откатывает `QuizAnswer` и изменение `UserWordProgress`;
- существующие тесты тестирования остаются зелёными при включённом и выключенном флаге.

---

#### [P4.T4] Добавить неавторитетное теневое сравнение

**Уровень:** Standard

**Файлы:**

```changeset
+ backend/app/services/shadow_comparison_service.py
~ backend/app/services/next_activity_service.py
+ backend/tests/test_shadow_comparison.py
```

**Референсы:**

- ALG-03 в [P3.T2]
- текущие селекторы срока и новых слов в `backend/app/services/learning_service.py`

**Что сделать:**

После green learning/quiz adapters WS-C рассчитывает необязательное внутреннее решение селектора
для сравнения. Оно не влияет на ответ, текущую очередь или состояние. Структурированный результат
содержит версию политики, намерение текущей модели, выбранную цель, коды причин и категорию различия.

**Ключевые ограничения:**

- сырые ответы ученика, текст перевода и ID пользователя не попадают в журналы приложения;
- селектор не меняет состояние во время сравнения;
- сбой сравнения не откатывает уже валидное событие или проекцию: это только диагностика;
- адаптер метрик и журналирования остаётся сменным и отключается независимо.

**Проверка:**

- сравнение возвращает стабильные категории расхождения для due/new/weak;
- состояние селектора остаётся неизменным;
- тесты редактирования запрещают ID ученика и текст ответа в журналах;
- выключенный флаг не выполняет сравнение.

---

#### [P4.T5] Выполнить G4 regression и обновить долговечную документацию

**Уровень:** Standard

**Файлы:**

```changeset
~ backend/tests/test_migrations.py
+ backend/tests/test_domain_shadow_integration.py
~ docs/product-state.md
~ docs/progress/PROGRESS.md
```

**Референсы:**

- команды проверки из `README.md`
- правила ведения `docs/product-state.md`
- реестр фаз и контрактов в `docs/progress/PROGRESS.md`

**Что сделать:**

INT объединяет только green P4.T2/P4.T3/P4.T4 commits, запускает полный lint/backend suite с
выключенным флагом и целевые shadow tests с включённым. PostgreSQL проверяет migration,
idempotency и concurrent review/quiz writes. Product state фиксирует только реализованное, а
progress-файл — статусы фаз и evidence проверки.

**Ключевые ограничения:**

- документация не заявляет о реализации frontend или единого учебного потока;
- production flag остаётся запрещённым до отдельного retention/export/delete решения и либо real
  auth, либо явно принятого ограничения на non-public trusted deployment;
- ошибки переданной конфигурации PostgreSQL завершают проверку ошибкой, а не пропуском;
- несвязанные артефакты `.superpowers/` остаются нетронутыми;
- этот SDD не меняет frontend-файлы и тесты.

**Проверка:**

- `cd backend && .venv/bin/ruff check .`;
- `cd backend && .venv/bin/pytest -v`;
- цель миграции и конкурентности на PostgreSQL;
- `git diff --check` и аудит намеренно изменённых файлов.

## Проверка фазы

**Автотесты:** полная регрессия текущего backend, теневая интеграция с включённым флагом, атомарный
откат, идемпотентность, владение, редактирование журналов и конкурентность PostgreSQL.

**Откат:** установить `LANGUAGE_ASSISTANT_SHADOW_ENABLED=false` для немедленного возврата поведения.
Откат кода оставляет дополнительные таблицы и данные неиспользуемыми. Понижение миграции необязательно
и выполняется только после подтверждения, что теневые данные можно удалить.
