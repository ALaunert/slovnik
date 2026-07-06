# Serbian Vocabulary Trainer MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a responsive Vue + Python + Postgres MVP for Serbian vocabulary learning with lightweight `userId` access, global vocabulary management, daily learning, review, quizzes, weekly quizzes, and Russian/Serbian UI support.

**Architecture:** Use a FastAPI backend as the source of truth, SQLAlchemy/Alembic for Postgres persistence, and a Vue 3/Vite frontend for the learner and editor flows. Keep vocabulary content global while storing profile, progress, quiz attempts, and weak-word state per `userId`. Implement the MVP as vertical slices so each task leaves the app runnable and testable.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Pydantic, pytest, Postgres, Vue 3, Vite, TypeScript, Vitest, Vue Test Utils, Playwright, Docker Compose.

---

## Source Specs

- Product brief: `artifacts/product.md`
- PRD: `artifacts/prd.md`
- Task outline: `artifacts/tasks.md`
- Implementation skill: @superpowers:subagent-driven-development or @superpowers:executing-plans
- Testing skill for each code task: @superpowers:test-driven-development
- Verification skill before completion: @superpowers:verification-before-completion

## Scope Check

The PRD covers a full MVP across backend, frontend, database, and responsive UX. It is still one cohesive product because each subsystem depends on the same core vocabulary/progress model, so this plan keeps it together as a single implementation sequence. If the team wants smaller standalone plans later, split after Task 3 into Vocabulary Management, Learning Sessions, and Quiz/Review plans.

## File Structure

Create the app as a two-package repository with shared local development tooling:

```text
.
├── README.md
├── docker-compose.yml
├── .env.example
├── backend/
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── db.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── seed.py
│   │   ├── services/
│   │   │   ├── vocabulary_service.py
│   │   │   ├── profile_service.py
│   │   │   ├── learning_service.py
│   │   │   └── quiz_service.py
│   │   └── routers/
│   │       ├── health.py
│   │       ├── profiles.py
│   │       ├── vocabulary.py
│   │       ├── learning.py
│   │       └── quizzes.py
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   └── tests/
│       ├── conftest.py
│       ├── test_health.py
│       ├── test_profiles.py
│       ├── test_vocabulary.py
│       ├── test_learning.py
│       └── test_quizzes.py
└── frontend/
    ├── package.json
    ├── index.html
    ├── vite.config.ts
    ├── playwright.config.ts
    ├── tsconfig.json
    ├── src/
    │   ├── main.ts
    │   ├── App.vue
    │   ├── api/client.ts
    │   ├── router.ts
    │   ├── stores/session.ts
    │   ├── i18n/messages.ts
    │   ├── views/
    │   │   ├── UserAccessView.vue
    │   │   ├── DashboardView.vue
    │   │   ├── VocabularyListView.vue
    │   │   ├── WordEditorView.vue
    │   │   ├── NewWordsView.vue
    │   │   ├── ReviewView.vue
    │   │   ├── QuizView.vue
    │   │   └── ResultsView.vue
    │   ├── components/
    │   │   ├── AppShell.vue
    │   │   ├── WordCard.vue
    │   │   ├── SessionProgress.vue
    │   │   ├── FeedbackPanel.vue
    │   │   └── EmptyState.vue
    │   └── styles.css
    └── tests/
        ├── unit/
        └── e2e/
```

Responsibility boundaries:

- `backend/app/models.py`: SQLAlchemy table definitions only.
- `backend/app/schemas.py`: Pydantic request/response contracts only.
- `backend/app/services/*`: business rules for selection, progress, and quiz behavior.
- `backend/app/routers/*`: HTTP routes only, thin wrappers over services.
- `frontend/src/api/client.ts`: typed API wrapper only.
- `frontend/src/stores/session.ts`: `userId`, editor token, profile settings, and browser storage.
- `frontend/src/views/*`: route-level workflows.
- `frontend/src/components/*`: reusable UI primitives for cards, progress, feedback, and empty states.

---

### Task 1: Repository Foundation

**Files:**
- Create: `docker-compose.yml`
- Create: `.env.example`
- Create: `backend/pyproject.toml`
- Create: `backend/app/main.py`
- Create: `backend/app/config.py`
- Create: `backend/app/db.py`
- Create: `backend/app/routers/health.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_health.py`
- Create: `frontend/package.json`
- Create: `frontend/index.html`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/src/main.ts`
- Create: `frontend/src/App.vue`
- Create: `frontend/src/styles.css`
- Modify: `README.md`

- [ ] **Step 1: Write the backend health test**

Create `backend/tests/test_health.py`:

```python
from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_ok():
    client = TestClient(app)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: Run backend test to verify it fails**

Run:

```bash
cd backend
pytest tests/test_health.py -v
```

Expected: FAIL because `app.main` or `/api/health` does not exist yet.

- [ ] **Step 3: Add backend project and health endpoint**

Create `backend/pyproject.toml`:

```toml
[project]
name = "serbian-vocabulary-trainer-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "alembic>=1.13",
  "fastapi>=0.115",
  "psycopg[binary]>=3.2",
  "pydantic-settings>=2.4",
  "sqlalchemy>=2.0",
  "uvicorn[standard]>=0.30",
]

[project.optional-dependencies]
dev = [
  "httpx>=0.27",
  "pytest>=8.3",
  "pytest-asyncio>=0.24",
  "ruff>=0.6",
]

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]

[tool.ruff]
line-length = 100
```

Create `backend/app/config.py`:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://slovnik:slovnik@localhost:5432/slovnik"
    editor_password: str = "dev-editor-password"
    cors_origins: list[str] = ["http://localhost:5173"]

    model_config = SettingsConfigDict(env_file="../.env", env_file_encoding="utf-8")


settings = Settings()
```

Create `backend/app/db.py`:

```python
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

Create `backend/app/routers/health.py`:

```python
from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

Create `backend/app/main.py`:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import health

app = FastAPI(title="Serbian Vocabulary Trainer")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health.router)
```

- [ ] **Step 4: Run backend test to verify it passes**

Run:

```bash
cd backend
pytest tests/test_health.py -v
```

Expected: PASS.

- [ ] **Step 5: Add local Postgres and frontend shell**

Create `docker-compose.yml`:

```yaml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: slovnik
      POSTGRES_USER: slovnik
      POSTGRES_PASSWORD: slovnik
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

Create `.env.example`:

```env
DATABASE_URL=postgresql+psycopg://slovnik:slovnik@localhost:5432/slovnik
EDITOR_PASSWORD=change-me
VITE_API_BASE_URL=http://localhost:8000
```

Create the minimal Vite app:

```json
{
  "scripts": {
    "dev": "vite --host 0.0.0.0",
    "build": "vue-tsc -b && vite build",
    "test:unit": "vitest run",
    "test:e2e": "playwright test"
  },
  "dependencies": {
    "@vitejs/plugin-vue": "^5.1.0",
    "vue": "^3.5.0",
    "vue-router": "^4.4.0"
  },
  "devDependencies": {
    "@playwright/test": "^1.46.0",
    "@vue/test-utils": "^2.4.6",
    "jsdom": "^25.0.0",
    "typescript": "^5.5.0",
    "vite": "^5.4.0",
    "vitest": "^2.0.0",
    "vue-tsc": "^2.0.0"
  }
}
```

Create `frontend/vite.config.ts` with a browser-like Vitest environment:

```ts
import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [vue()],
  test: {
    environment: "jsdom",
  },
});
```

Use `frontend/src/App.vue`:

```vue
<template>
  <main class="app-shell">
    <h1>Сербский словарь</h1>
    <p>Тренажер лексики готов к запуску.</p>
  </main>
</template>
```

- [ ] **Step 6: Document local setup**

Update `README.md` with:

```markdown
## Local Development

1. Copy `.env.example` to `.env`.
2. Start Postgres: `docker compose up -d postgres`.
3. Start backend: `cd backend && uvicorn app.main:app --reload`.
4. Start frontend: `cd frontend && npm install && npm run dev`.
5. Check backend: `curl http://localhost:8000/api/health`.
```

- [ ] **Step 7: Verify foundation commands**

Run:

```bash
cd backend && pytest -v
cd frontend && npm install && npm run build
```

Expected: backend tests pass and frontend build succeeds.

- [ ] **Step 8: Commit**

```bash
git add README.md .env.example docker-compose.yml backend frontend
git commit -m "chore: scaffold vocabulary trainer app"
```

---

### Task 2: Database Schema and Seed Data

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/versions/20260702_0001_initial_schema.py`
- Create: `backend/app/models.py`
- Create: `backend/app/schemas.py`
- Create: `backend/app/seed.py`
- Modify: `backend/app/db.py`
- Modify: `backend/tests/conftest.py`
- Create: `backend/tests/test_schema.py`

- [ ] **Step 1: Write schema tests**

Create `backend/tests/test_schema.py`:

```python
from sqlalchemy import select

from app.models import UserProfile, VocabularyItem


def test_can_create_vocabulary_item(db_session):
    word = VocabularyItem(
        serbian_cyrillic="хвала",
        serbian_latin="hvala",
        russian_translation="спасибо",
        cefr_level="A1",
        theme="greetings",
    )

    db_session.add(word)
    db_session.commit()

    saved = db_session.scalar(select(VocabularyItem).where(VocabularyItem.serbian_latin == "hvala"))
    assert saved is not None
    assert saved.serbian_cyrillic == "хвала"


def test_can_create_user_profile(db_session):
    profile = UserProfile(user_id="learner-1", preferred_level="A1", daily_new_word_count=5)

    db_session.add(profile)
    db_session.commit()

    saved = db_session.get(UserProfile, "learner-1")
    assert saved is not None
    assert saved.daily_new_word_count == 5
```

- [ ] **Step 2: Run schema tests to verify they fail**

Run:

```bash
cd backend
pytest tests/test_schema.py -v
```

Expected: FAIL because `app.models` does not exist yet.

- [ ] **Step 3: Implement SQLAlchemy models**

Create `backend/app/models.py`:

```python
from datetime import datetime
from typing import Literal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

CEFRLevel = Literal["A1", "A2", "B1", "B2", "C1", "C2"]


class VocabularyItem(Base):
    __tablename__ = "vocabulary_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    serbian_cyrillic: Mapped[str] = mapped_column(String(160), nullable=False)
    serbian_latin: Mapped[str] = mapped_column(String(160), nullable=False)
    russian_translation: Mapped[str] = mapped_column(String(240), nullable=False)
    cefr_level: Mapped[str] = mapped_column(String(2), nullable=False, index=True)
    theme: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    usage_register: Mapped[str | None] = mapped_column(String(80))
    stress_marker: Mapped[str | None] = mapped_column(String(160))
    meaning_notes: Mapped[str | None] = mapped_column(Text)
    example_sentences: Mapped[str | None] = mapped_column(Text)
    example_translations: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class UserProfile(Base):
    __tablename__ = "user_profiles"

    user_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    preferred_level: Mapped[str] = mapped_column(String(2), default="A1")
    daily_new_word_count: Mapped[int] = mapped_column(Integer, default=5)
    ui_language: Mapped[str] = mapped_column(String(8), default="ru")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserWordProgress(Base):
    __tablename__ = "user_word_progress"
    __table_args__ = (UniqueConstraint("user_id", "word_id", name="uq_user_word_progress"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.user_id"), index=True)
    word_id: Mapped[int] = mapped_column(ForeignKey("vocabulary_items.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="new")
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_quizzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    incorrect_count: Mapped[int] = mapped_column(Integer, default=0)
    is_weak: Mapped[bool] = mapped_column(Boolean, default=False)
    weak_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    word: Mapped[VocabularyItem] = relationship()


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.user_id"), index=True)
    quiz_type: Mapped[str] = mapped_column(String(20), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    score: Mapped[int] = mapped_column(Integer, default=0)
    total_questions: Mapped[int] = mapped_column(Integer, default=0)


class QuizAnswer(Base):
    __tablename__ = "quiz_answers"

    id: Mapped[int] = mapped_column(primary_key=True)
    quiz_attempt_id: Mapped[int] = mapped_column(ForeignKey("quiz_attempts.id"), index=True)
    word_id: Mapped[int] = mapped_column(ForeignKey("vocabulary_items.id"), index=True)
    question_type: Mapped[str] = mapped_column(String(40), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 4: Add test database fixture**

Update `backend/tests/conftest.py`:

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    TestingSession = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)
    with TestingSession() as session:
        yield session
    Base.metadata.drop_all(engine)
```

- [ ] **Step 5: Run schema tests**

Run:

```bash
cd backend
pytest tests/test_schema.py -v
```

Expected: PASS.

- [ ] **Step 6: Add Alembic migration**

Create Alembic config/env files and `backend/alembic/versions/20260702_0001_initial_schema.py` with tables matching `models.py`. The migration must create:

- `vocabulary_items`
- `user_profiles`
- `user_word_progress`
- `quiz_attempts`
- `quiz_answers`

Use indexes on `cefr_level`, `theme`, `user_id`, and `word_id`.

- [ ] **Step 7: Add seed data**

Create `backend/app/seed.py`:

```python
from sqlalchemy.orm import Session

from app.models import VocabularyItem

SAMPLE_WORDS = [
    {
        "serbian_cyrillic": "хвала",
        "serbian_latin": "hvala",
        "russian_translation": "спасибо",
        "cefr_level": "A1",
        "theme": "greetings",
        "usage_register": "common",
    },
    {
        "serbian_cyrillic": "молим",
        "serbian_latin": "molim",
        "russian_translation": "пожалуйста",
        "cefr_level": "A1",
        "theme": "greetings",
        "usage_register": "common",
    },
    {
        "serbian_cyrillic": "вода",
        "serbian_latin": "voda",
        "russian_translation": "вода",
        "cefr_level": "A1",
        "theme": "daily-life",
        "usage_register": "common",
    },
]


def seed_words(db: Session) -> int:
    created = 0
    for item in SAMPLE_WORDS:
        exists = (
            db.query(VocabularyItem)
            .filter(VocabularyItem.serbian_latin == item["serbian_latin"])
            .first()
        )
        if exists:
            continue
        db.add(VocabularyItem(**item))
        created += 1
    db.commit()
    return created


if __name__ == "__main__":
    from app.db import SessionLocal

    with SessionLocal() as db:
        created = seed_words(db)
    print(f"Seeded {created} vocabulary words.")
```

- [ ] **Step 8: Verify migrations**

Run:

```bash
docker compose up -d postgres
cd backend
alembic upgrade head
```

Expected: migration succeeds against local Postgres.

- [ ] **Step 9: Commit**

```bash
git add backend docker-compose.yml
git commit -m "feat: add database schema"
```

---

### Task 3: User ID Access and Dashboard

**Files:**
- Create: `backend/app/services/profile_service.py`
- Create: `backend/app/routers/profiles.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/schemas.py`
- Create: `backend/tests/test_profiles.py`
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/router.ts`
- Create: `frontend/src/stores/session.ts`
- Create: `frontend/src/views/UserAccessView.vue`
- Create: `frontend/src/views/DashboardView.vue`
- Create: `frontend/tests/unit/session.test.ts`
- Modify: `frontend/src/App.vue`
- Modify: `frontend/src/main.ts`

- [ ] **Step 1: Write backend profile tests**

Create `backend/tests/test_profiles.py`:

```python
from fastapi.testclient import TestClient

from app.main import app


def test_create_or_load_profile(client: TestClient):
    response = client.post("/api/profiles", json={"user_id": "learner-1"})

    assert response.status_code == 200
    assert response.json()["user_id"] == "learner-1"
    assert response.json()["preferred_level"] == "A1"
    assert response.json()["daily_new_word_count"] == 5


def test_update_profile_settings(client: TestClient):
    client.post("/api/profiles", json={"user_id": "learner-1"})

    response = client.patch(
        "/api/profiles/learner-1",
        json={"preferred_level": "A2", "daily_new_word_count": 7, "ui_language": "sr"},
    )

    assert response.status_code == 200
    assert response.json()["preferred_level"] == "A2"
    assert response.json()["daily_new_word_count"] == 7
    assert response.json()["ui_language"] == "sr"
```

Update `backend/tests/conftest.py` to expose `client` with dependency override for the in-memory `db_session`.

- [ ] **Step 2: Run profile tests to verify they fail**

Run:

```bash
cd backend
pytest tests/test_profiles.py -v
```

Expected: FAIL with 404 for `/api/profiles`.

- [ ] **Step 3: Add profile schemas, service, and routes**

Add to `backend/app/schemas.py`:

```python
from pydantic import BaseModel, Field


class ProfileCreate(BaseModel):
    user_id: str = Field(min_length=1, max_length=80)


class ProfileUpdate(BaseModel):
    preferred_level: str | None = None
    daily_new_word_count: int | None = Field(default=None, ge=1, le=50)
    ui_language: str | None = None


class ProfileRead(BaseModel):
    user_id: str
    preferred_level: str
    daily_new_word_count: int
    ui_language: str

    model_config = {"from_attributes": True}
```

Create `backend/app/services/profile_service.py`:

```python
from sqlalchemy.orm import Session

from app.models import UserProfile
from app.schemas import ProfileUpdate


def get_or_create_profile(db: Session, user_id: str) -> UserProfile:
    profile = db.get(UserProfile, user_id)
    if profile:
        return profile
    profile = UserProfile(user_id=user_id)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def update_profile(db: Session, user_id: str, update: ProfileUpdate) -> UserProfile:
    profile = get_or_create_profile(db, user_id)
    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return profile
```

Create `backend/app/routers/profiles.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import ProfileCreate, ProfileRead, ProfileUpdate
from app.services.profile_service import get_or_create_profile, update_profile

router = APIRouter(prefix="/api/profiles", tags=["profiles"])


@router.post("", response_model=ProfileRead)
def create_or_load_profile(payload: ProfileCreate, db: Session = Depends(get_db)):
    return get_or_create_profile(db, payload.user_id)


@router.patch("/{user_id}", response_model=ProfileRead)
def patch_profile(user_id: str, payload: ProfileUpdate, db: Session = Depends(get_db)):
    return update_profile(db, user_id, payload)
```

Include router in `backend/app/main.py`.

- [ ] **Step 4: Verify backend profile tests pass**

Run:

```bash
cd backend
pytest tests/test_profiles.py -v
```

Expected: PASS.

- [ ] **Step 5: Write frontend session store tests**

Create `frontend/tests/unit/session.test.ts`:

```ts
import { describe, expect, it, vi } from "vitest";
import { createSessionStore } from "../../src/stores/session";

describe("session store", () => {
  it("persists the last user id", () => {
    const storage = new Map<string, string>();
    const store = createSessionStore({
      getItem: (key) => storage.get(key) ?? null,
      setItem: (key, value) => storage.set(key, value),
      removeItem: (key) => storage.delete(key),
    });

    store.setUserId("learner-1");

    expect(storage.get("slovnik.userId")).toBe("learner-1");
    expect(store.userId.value).toBe("learner-1");
  });
});
```

- [ ] **Step 6: Implement frontend access flow**

Create `frontend/src/stores/session.ts`:

```ts
import { ref } from "vue";

const USER_ID_KEY = "slovnik.userId";

export function createSessionStore(storage: Storage) {
  const userId = ref(storage.getItem(USER_ID_KEY) ?? "");

  function setUserId(nextUserId: string) {
    userId.value = nextUserId;
    storage.setItem(USER_ID_KEY, nextUserId);
  }

  function clearUserId() {
    userId.value = "";
    storage.removeItem(USER_ID_KEY);
  }

  return { userId, setUserId, clearUserId };
}

export const sessionStore = createSessionStore(window.localStorage);
```

Create `frontend/src/api/client.ts`:

```ts
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export async function createOrLoadProfile(userId: string) {
  const response = await fetch(`${API_BASE_URL}/api/profiles`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId }),
  });
  if (!response.ok) throw new Error("Failed to load profile");
  return response.json();
}

export async function updateProfile(
  userId: string,
  payload: { preferred_level?: string; daily_new_word_count?: number; ui_language?: string },
) {
  const response = await fetch(`${API_BASE_URL}/api/profiles/${encodeURIComponent(userId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error("Failed to update profile");
  return response.json();
}
```

Create routes for `/`, `/dashboard`, and basic dashboard action links. Keep copy Russian-first with concise Serbian labels where helpful.

In `DashboardView.vue`, include a compact settings section backed by the loaded profile:

- CEFR selector with `A1`, `A2`, `B1`, `B2`, `C1`, `C2`.
- Daily new word count numeric input, clamped from 1 to 50.
- UI language selector with Russian and Serbian.
- Save button calling `updateProfile(userId, payload)`.
- Success and error states that do not block the main daily actions.

Add or update a frontend unit test asserting the dashboard sends:

```ts
{
  preferred_level: "A2",
  daily_new_word_count: 7,
  ui_language: "sr"
}
```

- [ ] **Step 7: Run frontend tests and build**

Run:

```bash
cd frontend
npm run test:unit
npm run build
```

Expected: unit tests pass and app builds.

- [ ] **Step 8: Commit**

```bash
git add backend frontend
git commit -m "feat: add user id access"
```

---

### Task 4: Vocabulary Editor and Vocabulary List

**Files:**
- Create: `backend/app/services/vocabulary_service.py`
- Create: `backend/app/routers/vocabulary.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/schemas.py`
- Create: `backend/tests/test_vocabulary.py`
- Create: `frontend/src/views/VocabularyListView.vue`
- Create: `frontend/src/views/WordEditorView.vue`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/router.ts`
- Create: `frontend/tests/unit/vocabulary.test.ts`

- [ ] **Step 1: Write backend vocabulary tests**

Create tests for:

```python
def test_editor_can_create_word_with_password(client):
    response = client.post(
        "/api/vocabulary",
        headers={"X-Editor-Password": "dev-editor-password"},
        json={
            "serbian_cyrillic": "добар дан",
            "serbian_latin": "dobar dan",
            "russian_translation": "добрый день",
            "cefr_level": "A1",
            "theme": "greetings",
        },
    )
    assert response.status_code == 201
    assert response.json()["serbian_latin"] == "dobar dan"


def test_create_word_rejects_wrong_editor_password(client):
    response = client.post("/api/vocabulary", headers={"X-Editor-Password": "bad"}, json={})
    assert response.status_code == 403


def test_list_words_filters_by_level_and_theme(client, db_session):
    # Seed A1 greetings and A2 food words, then assert only matching words return.
```

- [ ] **Step 2: Run vocabulary tests to verify they fail**

Run:

```bash
cd backend
pytest tests/test_vocabulary.py -v
```

Expected: FAIL with 404 for vocabulary routes.

- [ ] **Step 3: Add schemas and password guard**

Add Pydantic schemas:

```python
class VocabularyCreate(BaseModel):
    serbian_cyrillic: str = Field(min_length=1, max_length=160)
    serbian_latin: str = Field(min_length=1, max_length=160)
    russian_translation: str = Field(min_length=1, max_length=240)
    cefr_level: str
    theme: str
    usage_register: str | None = None
    stress_marker: str | None = None
    meaning_notes: str | None = None
    example_sentences: str | None = None
    example_translations: str | None = None


class VocabularyUpdate(VocabularyCreate):
    pass


class VocabularyRead(VocabularyCreate):
    id: int

    model_config = {"from_attributes": True}
```

Use a router dependency:

```python
from fastapi import Header, HTTPException, status

def require_editor_password(x_editor_password: str = Header(default="")) -> None:
    if x_editor_password != settings.editor_password:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid editor password")
```

- [ ] **Step 4: Add vocabulary service and routes**

Implement:

- `POST /api/vocabulary` with editor password.
- `PUT /api/vocabulary/{word_id}` with editor password.
- `GET /api/vocabulary?cefr_level=A1&theme=greetings`.
- `GET /api/vocabulary/themes`.

Filtering must be optional and combinable.

- [ ] **Step 5: Run backend vocabulary tests**

Run:

```bash
cd backend
pytest tests/test_vocabulary.py -v
```

Expected: PASS.

- [ ] **Step 6: Build frontend vocabulary list**

Create `VocabularyListView.vue` with:

- CEFR select.
- Theme select.
- Dense list showing Cyrillic, Latin, Russian translation, level, and theme.
- Edit link visible after editor password is accepted.

- [ ] **Step 7: Build frontend word editor**

Create `WordEditorView.vue` with:

- Editor password field.
- Required inputs for Cyrillic, Latin, Russian translation, CEFR, and theme.
- Optional fields for stress, notes, usage register, examples, and translations.
- Save state and validation errors.

- [ ] **Step 8: Verify frontend**

Run:

```bash
cd frontend
npm run test:unit
npm run build
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add backend frontend
git commit -m "feat: add vocabulary management"
```

---

### Task 5: Daily New Words Session

**Files:**
- Create: `backend/app/services/learning_service.py`
- Create: `backend/app/routers/learning.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/schemas.py`
- Create: `backend/tests/test_learning.py`
- Create: `frontend/src/views/NewWordsView.vue`
- Create: `frontend/src/components/WordCard.vue`
- Create: `frontend/src/components/SessionProgress.vue`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/router.ts`

- [ ] **Step 1: Write daily selection tests**

Create tests for:

```python
def test_daily_new_words_prefers_unseen_words_for_user(client, seeded_words):
    response = client.get("/api/learning/learner-1/new-words")
    assert response.status_code == 200
    assert len(response.json()["words"]) == 5


def test_complete_new_words_records_first_seen_progress(client, seeded_words):
    word_ids = [seeded_words[0].id, seeded_words[1].id]
    response = client.post("/api/learning/learner-1/new-words/complete", json={"word_ids": word_ids})
    assert response.status_code == 200
    assert all(item["status"] == "seen" for item in response.json()["progress"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd backend
pytest tests/test_learning.py -v
```

Expected: FAIL because learning routes do not exist.

- [ ] **Step 3: Implement learning service**

Implement:

```python
def get_daily_new_words(db: Session, user_id: str) -> list[VocabularyItem]:
    profile = get_or_create_profile(db, user_id)
    seen_word_ids = select(UserWordProgress.word_id).where(UserWordProgress.user_id == user_id)
    return list(
        db.scalars(
            select(VocabularyItem)
            .where(VocabularyItem.cefr_level == profile.preferred_level)
            .where(VocabularyItem.id.not_in(seen_word_ids))
            .order_by(VocabularyItem.id)
            .limit(profile.daily_new_word_count)
        )
    )
```

Implement completion:

- Create progress if absent.
- Set `status="seen"`.
- Set `first_seen_at` if absent.
- Set `last_seen_at=now`.

- [ ] **Step 4: Add learning routes**

Add:

- `GET /api/learning/{user_id}/new-words`
- `POST /api/learning/{user_id}/new-words/complete`

- [ ] **Step 5: Run backend tests**

Run:

```bash
cd backend
pytest tests/test_learning.py -v
```

Expected: PASS.

- [ ] **Step 6: Build card-by-card frontend**

Create `WordCard.vue` displaying:

- Serbian Cyrillic.
- Serbian Latin.
- Russian translation.
- CEFR level.
- Theme.
- Optional notes and examples when present.

Create `NewWordsView.vue`:

- Loads `GET /api/learning/{userId}/new-words`.
- Shows one card at a time.
- Uses stable previous/next/complete controls.
- Calls completion endpoint after final card.
- Shows an understandable empty state when no new words are available.

- [ ] **Step 7: Verify**

Run:

```bash
cd backend && pytest tests/test_learning.py -v
cd frontend && npm run build
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend frontend
git commit -m "feat: add daily new word sessions"
```

---

### Task 6: Review Mode

**Files:**
- Modify: `backend/app/services/learning_service.py`
- Modify: `backend/app/routers/learning.py`
- Modify: `backend/app/schemas.py`
- Modify: `backend/tests/test_learning.py`
- Create: `frontend/src/views/ReviewView.vue`
- Create: `frontend/src/components/EmptyState.vue`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/router.ts`

- [ ] **Step 1: Write review selection tests**

Add tests:

```python
def test_review_includes_weak_words(client, db_session, weak_progress):
    response = client.get("/api/learning/learner-1/review")
    assert response.status_code == 200
    assert weak_progress.word_id in [word["id"] for word in response.json()["words"]]


def test_review_avoids_words_seen_today_when_not_weak(client, db_session, seen_today_progress):
    response = client.get("/api/learning/learner-1/review")
    assert seen_today_progress.word_id not in [word["id"] for word in response.json()["words"]]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd backend
pytest tests/test_learning.py::test_review_includes_weak_words tests/test_learning.py::test_review_avoids_words_seen_today_when_not_weak -v
```

Expected: FAIL because review endpoint does not exist.

- [ ] **Step 3: Implement simple review rule**

Use this MVP rule:

- Include weak words first.
- Include seen/reviewing words where `last_seen_at` is null or before today.
- Exclude words first seen today unless `is_weak=true`.
- Limit to 20 words.

Add `GET /api/learning/{user_id}/review` and `POST /api/learning/{user_id}/review/complete`.

Review completion behavior:

- Accept `word_ids` for the words the user actually reviewed.
- For each progress row, set `status="reviewing"` unless it is already `learned`.
- Set `last_seen_at=now` so non-weak words do not immediately reappear the same day.
- Do not clear `is_weak`; weak status changes only through quiz answers.
- Return updated progress rows so the frontend can show completion state.

- [ ] **Step 4: Run backend tests**

Run:

```bash
cd backend
pytest tests/test_learning.py -v
```

Expected: PASS.

- [ ] **Step 5: Build review frontend**

Create `ReviewView.vue`:

- Separate route from new words.
- Shows weak badge for `is_weak`.
- Shows previously failed copy when `incorrect_count > 0`.
- Uses same `WordCard` and `SessionProgress`.
- Calls review completion endpoint.

- [ ] **Step 6: Verify**

Run:

```bash
cd backend && pytest tests/test_learning.py -v
cd frontend && npm run build
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend frontend
git commit -m "feat: add review sessions"
```

---

### Task 7: Daily Quiz Mode

**Files:**
- Create: `backend/app/services/quiz_service.py`
- Create: `backend/app/routers/quizzes.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/schemas.py`
- Create: `backend/tests/test_quizzes.py`
- Create: `frontend/src/views/QuizView.vue`
- Create: `frontend/src/views/ResultsView.vue`
- Create: `frontend/src/components/FeedbackPanel.vue`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/router.ts`

- [ ] **Step 1: Write quiz backend tests**

Create tests:

```python
def test_start_daily_quiz_returns_supported_question_types(client, completed_learning):
    response = client.post("/api/quizzes/learner-1/start", json={"quiz_type": "daily"})
    assert response.status_code == 200
    question_types = {question["question_type"] for question in response.json()["questions"]}
    assert "sr_to_ru_choice" in question_types
    assert "ru_to_sr_typing" in question_types
    assert "remembered_forgot_self_check" in question_types


def test_submit_incorrect_answer_marks_word_weak(client, started_quiz):
    question = started_quiz["questions"][0]
    response = client.post(
        f"/api/quizzes/{started_quiz['attempt_id']}/answers",
        json={"word_id": question["word_id"], "question_type": question["question_type"], "answer": "wrong"},
    )
    assert response.status_code == 200
    assert response.json()["is_correct"] is False
    assert response.json()["repeat_word"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd backend
pytest tests/test_quizzes.py -v
```

Expected: FAIL because quiz routes do not exist.

- [ ] **Step 3: Implement quiz question generation**

Daily quiz source words:

- Words learned or reviewed by the user.
- Prefer words touched today.
- Include weak words.

Question types:

- `sr_to_ru_choice`: prompt with Serbian Cyrillic and Latin, answer is Russian translation, choices are Russian translations.
- `ru_to_sr_typing`: prompt with Russian translation, answer accepts Serbian Latin or Cyrillic case-insensitively.
- `remembered_forgot_self_check`: prompt with Serbian Cyrillic and Latin, reveal Russian translation after the learner chooses to check, then accept `remembered` or `forgot` as the answer. Treat `forgot` as incorrect and `remembered` as correct.

Distractor rule:

- Same CEFR first.
- Same theme when possible.
- Exclude the correct word.
- Return 4 choices when enough vocabulary exists.

- [ ] **Step 4: Implement answer submission**

On answer:

- Create `QuizAnswer`.
- Increment `correct_count` or `incorrect_count`.
- Set `last_quizzed_at`.
- If incorrect, set `is_weak=true`, `weak_since=now`, and tell frontend to repeat the word.
- If correct, leave weak state unchanged for daily quiz.
- For `remembered_forgot_self_check`, store `answer` as either `remembered` or `forgot`; `forgot` follows the same weak-word behavior as any other incorrect answer.

- [ ] **Step 5: Implement quiz completion**

Add `POST /api/quizzes/{attempt_id}/complete` returning:

```json
{
  "score": 3,
  "total_questions": 5,
  "weak_word_ids": [1, 4],
  "mistakes": []
}
```

- [ ] **Step 6: Run backend quiz tests**

Run:

```bash
cd backend
pytest tests/test_quizzes.py -v
```

Expected: PASS.

- [ ] **Step 7: Build quiz frontend**

Create `QuizView.vue`:

- Starts daily quiz for current `userId`.
- Shows one question at a time.
- Multiple choice buttons for `sr_to_ru_choice`.
- Text input for `ru_to_sr_typing`.
- Reveal/check controls for `remembered_forgot_self_check` with remembered and forgot buttons.
- Immediate `FeedbackPanel` after submit.
- Requeues incorrect words once in the same session.
- Completes attempt and navigates to results, passing the completion response so `ResultsView.vue` can show score, weak count, and mistake details.

Create `ResultsView.vue`:

- Shows score, total questions, weak word count, and mistakes.

- [ ] **Step 8: Verify**

Run:

```bash
cd backend && pytest tests/test_quizzes.py -v
cd frontend && npm run build
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add backend frontend
git commit -m "feat: add daily quiz mode"
```

---

### Task 8: Weekly Quiz

**Files:**
- Modify: `backend/app/services/quiz_service.py`
- Modify: `backend/app/routers/quizzes.py`
- Modify: `backend/app/schemas.py`
- Modify: `backend/tests/test_quizzes.py`
- Modify: `frontend/src/views/QuizView.vue`
- Modify: `frontend/src/views/DashboardView.vue`
- Modify: `frontend/src/views/ResultsView.vue`
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: Write weekly quiz tests**

Add tests:

```python
def test_weekly_quiz_includes_this_weeks_words_and_weak_words(client, weekly_progress):
    response = client.post("/api/quizzes/learner-1/start", json={"quiz_type": "weekly"})
    assert response.status_code == 200
    returned_ids = {question["word_id"] for question in response.json()["questions"]}
    assert weekly_progress["this_week_word_id"] in returned_ids
    assert weekly_progress["weak_word_id"] in returned_ids


def test_correct_weekly_answer_removes_weak_status(client, started_weekly_quiz, weak_word):
    question = next(q for q in started_weekly_quiz["questions"] if q["word_id"] == weak_word.id)
    answer = (
        weak_word.russian_translation
        if question["question_type"] == "sr_to_ru_choice"
        else weak_word.serbian_latin
    )

    response = client.post(
        f"/api/quizzes/{started_weekly_quiz['attempt_id']}/answers",
        json={
            "word_id": weak_word.id,
            "question_type": question["question_type"],
            "answer": answer,
        },
    )
    assert response.status_code == 200
    assert response.json()["is_correct"] is True
    assert response.json()["is_weak"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd backend
pytest tests/test_quizzes.py::test_weekly_quiz_includes_this_weeks_words_and_weak_words tests/test_quizzes.py::test_correct_weekly_answer_removes_weak_status -v
```

Expected: FAIL because weekly behavior is not implemented.

- [ ] **Step 3: Implement weekly source rule**

Weekly quiz words:

- Words whose `first_seen_at` or `last_seen_at` is within the current week.
- All current weak words.
- De-duplicate by `word_id`.
- Limit to 40 words for MVP.

- [ ] **Step 4: Implement weak removal for weekly quiz**

When a weak word is answered correctly in a weekly quiz:

- Set `is_weak=false`.
- Set `weak_since=null`.
- Increment `correct_count`.

When failed:

- Keep `is_weak=true`.
- Update `weak_since` if null.

- [ ] **Step 5: Run weekly tests**

Run:

```bash
cd backend
pytest tests/test_quizzes.py -v
```

Expected: PASS.

- [ ] **Step 6: Add weekly quiz UI entry point**

Update dashboard with a weekly quiz action. Reuse `QuizView.vue` with a route param or query param for `daily` versus `weekly`. Update results copy to show weekly summary wording.

- [ ] **Step 7: Verify**

Run:

```bash
cd backend && pytest tests/test_quizzes.py -v
cd frontend && npm run build
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend frontend
git commit -m "feat: add weekly quiz"
```

---

### Task 9: Russian/Serbian UI Copy and Responsive Polish

**Files:**
- Create: `frontend/src/i18n/messages.ts`
- Create: `frontend/src/components/AppShell.vue`
- Modify: `frontend/src/App.vue`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/src/views/UserAccessView.vue`
- Modify: `frontend/src/views/DashboardView.vue`
- Modify: `frontend/src/views/VocabularyListView.vue`
- Modify: `frontend/src/views/WordEditorView.vue`
- Modify: `frontend/src/views/NewWordsView.vue`
- Modify: `frontend/src/views/ReviewView.vue`
- Modify: `frontend/src/views/QuizView.vue`
- Modify: `frontend/src/views/ResultsView.vue`
- Create: `frontend/playwright.config.ts`
- Create: `frontend/tests/e2e/core-flow.spec.ts`

- [ ] **Step 1: Add copy catalog**

Create `frontend/src/i18n/messages.ts`:

```ts
export const messages = {
  ru: {
    appTitle: "Сербский словарь",
    dashboard: "Сегодня",
    newWords: "Новые слова",
    review: "Повторение",
    dailyQuiz: "Ежедневный тест",
    weeklyQuiz: "Недельный тест",
    vocabulary: "Словарь",
    editor: "Редактор",
    emptyVocabulary: "Пока нет слов. Добавьте первое слово в редакторе.",
    emptyReview: "На сегодня слов для повторения нет.",
  },
  sr: {
    appTitle: "Srpski rečnik",
    dashboard: "Danas",
    newWords: "Nove reči",
    review: "Ponavljanje",
    dailyQuiz: "Dnevni kviz",
    weeklyQuiz: "Nedeljni kviz",
    vocabulary: "Rečnik",
    editor: "Urednik",
    emptyVocabulary: "Još nema reči.",
    emptyReview: "Danas nema reči za ponavljanje.",
  },
} as const;
```

- [ ] **Step 2: Replace hard-coded English MVP copy**

Move route labels, empty states, buttons, and dashboard headings to Russian/Serbian copy. English can remain only in developer docs and tests.

- [ ] **Step 3: Implement responsive app shell**

Create `AppShell.vue` with:

- Header title.
- Compact navigation.
- Main content area.
- Mobile-safe spacing.

CSS requirements:

- No oversized marketing hero.
- Dense, calm app layout.
- Cards at `border-radius: 8px` or less.
- Stable button dimensions so text does not overflow.
- Comfortable one-column mobile layout.

- [ ] **Step 4: Write Playwright config and core-flow smoke test**

Create `frontend/playwright.config.ts`:

```ts
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  use: {
    baseURL: "http://127.0.0.1:5173",
  },
  webServer: {
    command: "npm run dev -- --host 127.0.0.1",
    url: "http://127.0.0.1:5173",
    reuseExistingServer: true,
  },
});
```

Create `frontend/tests/e2e/core-flow.spec.ts`:

```ts
import { expect, test } from "@playwright/test";

test("user can reach dashboard from user id entry", async ({ page }) => {
  await page.route("**/api/profiles", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        user_id: "learner-1",
        preferred_level: "A1",
        daily_new_word_count: 5,
        ui_language: "ru",
      }),
    });
  });

  await page.goto("/");
  await page.getByLabel("User ID").fill("learner-1");
  await page.getByRole("button", { name: /start|начать/i }).click();
  await expect(page.getByText("Сегодня")).toBeVisible();
});
```

If the label is localized, use the actual Russian label and keep the test aligned with UI copy. The smoke test mocks the profile API so `npm run test:e2e` does not require a live backend.

- [ ] **Step 5: Run responsive verification**

Run:

```bash
cd frontend
npm run build
npm run test:e2e
```

Expected: build succeeds and Playwright smoke test passes.

- [ ] **Step 6: Commit**

```bash
git add frontend
git commit -m "feat: polish responsive localized ui"
```

---

### Task 10: End-to-End Verification and Documentation

**Files:**
- Modify: `README.md`
- Create: `docs/testing/mvp-manual-test.md`
- Modify: backend and frontend tests only if verification exposes defects.

- [ ] **Step 1: Write manual MVP test script**

Create `docs/testing/mvp-manual-test.md`:

```markdown
# MVP Manual Test Script

## Setup

- Start Postgres with `docker compose up -d postgres`.
- Run migrations with `cd backend && alembic upgrade head`.
- Start backend with `cd backend && uvicorn app.main:app --reload`.
- Start frontend with `cd frontend && npm run dev`.

## Scenarios

1. Create or load `learner-1`.
2. Add at least 8 A1 vocabulary words through the editor.
3. Complete daily new words for `learner-1`.
4. Complete review for `learner-1`.
5. Fail one daily quiz answer and confirm the word becomes weak.
6. Create or load `learner-2` and confirm progress is separate.
7. Reopen with `learner-1` and confirm progress is still server-backed.
8. Start weekly quiz and answer the weak word correctly.
9. Confirm the weak word is removed from the weak list.
10. Check mobile width at 390px and desktop width at 1280px.
```

- [ ] **Step 2: Update README with full commands**

Add:

- Dependency installation commands.
- Migration commands.
- Seed data command.
- Backend tests.
- Frontend unit and e2e tests.
- Known MVP access caveat that `userId` is not secure authentication.

- [ ] **Step 3: Run backend verification**

Run:

```bash
cd backend
ruff check .
pytest -v
```

Expected: lint and tests pass.

- [ ] **Step 4: Run frontend verification**

Run:

```bash
cd frontend
npm run test:unit
npm run build
npm run test:e2e
```

Expected: unit tests, build, and e2e tests pass.

- [ ] **Step 5: Run database verification**

Run:

```bash
docker compose up -d postgres
cd backend
alembic downgrade base
alembic upgrade head
python -m app.seed
```

Expected: migrations rebuild a clean database and seed data inserts sample words without duplicates.

- [ ] **Step 6: Commit**

```bash
git add README.md docs/testing backend frontend
git commit -m "docs: add mvp verification guide"
```

---

## Final Acceptance Checklist

- [ ] Backend starts locally with `uvicorn app.main:app --reload`.
- [ ] Frontend starts locally with `npm run dev`.
- [ ] Postgres starts with `docker compose up -d postgres`.
- [ ] Migrations create all MVP tables.
- [ ] Health check returns `{"status":"ok"}`.
- [ ] A learner can enter a `userId` and reach the dashboard.
- [ ] Same `userId` loads the same server-backed progress from another browser.
- [ ] Editor password gates word creation and editing.
- [ ] Vocabulary list supports CEFR and theme filters.
- [ ] Daily new words respect preferred CEFR and daily count.
- [ ] New word completion creates per-user progress.
- [ ] Review mode is separate and includes weak words.
- [ ] Daily quiz supports Serbian-to-Russian multiple choice.
- [ ] Daily quiz supports Russian-to-Serbian typing.
- [ ] Incorrect quiz answers are repeated once in-session and marked weak.
- [ ] Weekly quiz includes this week's words plus weak words.
- [ ] Correct weekly answers remove weak status.
- [ ] Two users share global vocabulary but have separate progress.
- [ ] Core UI copy is Russian/Serbian.
- [ ] Core flows are comfortable at mobile and desktop widths.
- [ ] Deferred items remain out of scope: auth, audio, bulk import, AI, social, payments, advanced spaced repetition.
