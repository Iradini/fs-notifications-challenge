# Clean Architecture Map — from your FastAPI blog to the notifications app

This is a reference to **type from**, not to paste wholesale. It takes your real
blog code and shows where each responsibility moves in clean architecture, then
gives you the code for the pieces the blog doesn't have yet.

How to read it:
1. First, the mental model in one sentence.
2. Then your real `create_post` dissected — each line labelled with the layer it
   belongs to.
3. A side-by-side table: blog file → clean-architecture home.
4. The build order for the "send a notification" slice, with the code for each
   file. Each file is tagged **[ADAPTED]** (you already have this shape in the
   blog) or **[NEW]** (a concept the blog doesn't have — read the "why" note).

Assumed package layout: a uv `src` project whose package is `notifications`
(so `src/notifications/...`). If your package is named differently, change the
`notifications.` prefix in the imports to match.

---

## 1. The one sentence

**Dependencies point inward.** The business logic (domain, application) knows
nothing about FastAPI or SQLAlchemy. Those are outer details that plug in. Your
blog does the opposite — the route handler talks to SQLAlchemy directly. That's
not wrong, it's just *flat*. Clean architecture takes one flat handler and splits
its jobs across four layers so the core logic can be tested and changed without
touching the framework or the database.

The four layers, inside → out:
- **domain** — pure business objects and rules. No framework imports at all.
- **application** — use cases (the verbs) + repository *interfaces* (ports).
- **infrastructure** — the concrete DB/ORM/S3/email adapters.
- **interface** — FastAPI routes + Pydantic schemas.

---

## 2. Your real `create_post`, dissected

From `routers/posts.py`:

```python
@router.post("", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
async def create_post(
    post: PostCreate,                                    # (a)
    current_user: CurrentUser,                           # (b)
    db: Annotated[AsyncSession, Depends(get_db)],        # (c)
):
    new_post = models.Post(                              # (d)
        title=post.title,
        content=post.content,
        user_id=current_user.id,
    )
    db.add(new_post)                                     # (e)
    await db.commit()                                    # (e)
    await db.refresh(new_post, attribute_names=["author"])  # (e)
    return new_post                                      # (f)
```

One function is doing five different jobs. In clean architecture each job moves
to a different layer:

| Part | What it does | Clean-architecture home |
|------|--------------|--------------------------|
| (a) `post: PostCreate` | Parse + validate the HTTP body | **interface** (Pydantic schema) |
| (b) `current_user: CurrentUser` | Authenticate the caller | **interface** (dependency), backed by **infrastructure** (the JWT check in `auth.py`) |
| the implicit rule "a post must have an author, title, content" | Business rule | **domain** (entity invariant) + **application** (use case orchestrates) |
| (d) `models.Post(...)` | The ORM row | **infrastructure** (ORM model) |
| (e) `db.add / commit / refresh` | Persist to the database | **infrastructure** (repository) |
| (f) `return new_post` | Send the ORM object straight out | **interface** maps a **domain** object → response schema; the ORM object never leaves infrastructure |

The subtle lesson is in (d) and (f): your handler builds a SQLAlchemy object and
returns it directly, relying on `PostResponse`'s `from_attributes=True` to
serialize it. It works because the handler is thin. Clean architecture forbids
that shortcut on purpose — the ORM object is an infrastructure detail and must be
translated to a domain object before it crosses a boundary. That translation is
the part that will feel like busywork. It's the whole point.

---

## 3. Blog file → clean-architecture home

| In your blog (flat) | Moves to (clean) | Changes? |
|---------------------|------------------|----------|
| `database.py` (engine, `get_db`, `Base`) | `infrastructure/database.py` | Almost identical — **[ADAPTED]** |
| `config.py` (pydantic-settings) | `config.py` (top of package) | Identical — **[ADAPTED]** |
| `models.py` (SQLAlchemy ORM) | `infrastructure/models.py` | Same style, now clearly infra — **[ADAPTED]** |
| `schemas.py` (Pydantic) | `interface/schemas.py` | Same style — **[ADAPTED]** |
| `auth.py` / `CurrentUser` | `infrastructure/` + wired at interface | (skipped in slice 1) |
| the body of `create_post` (the rules) | `application/` use case | **[NEW]** concept |
| — (nothing like it in the blog) | `domain/` entity | **[NEW]** concept |
| — (nothing like it) | `application/ports.py` repository interface | **[NEW]** concept |
| the `db.add/commit` lines | `infrastructure/repository.py` | **[NEW]** shape (logic extracted from the handler) |
| `Depends(get_db)` wiring | composition in the route + `main.py` | **[NEW]** shape |

So three files you basically already know how to write (**[ADAPTED]**), and four
genuinely new ideas (**[NEW]**). The rest of this doc is the new ideas, in the
order you build them.

---

## 4. The "send a notification" slice — build order

No `User` model, no auth, no foreign keys yet: `sender_id` and `recipient_id` are
plain integers. That keeps this slice standalone (see the earlier reasoning).

Folder layout for just this slice:

```
src/notifications/
  config.py                      # [ADAPTED] from blog
  domain/
    notification.py              # [NEW]
  application/
    ports.py                     # [NEW]
    send_notification.py         # [NEW]
  infrastructure/
    database.py                  # [ADAPTED] from blog
    models.py                    # [ADAPTED] style
    repository.py                # [NEW]
  interface/
    schemas.py                   # [ADAPTED] style
    routes.py                    # [NEW] shape
  main.py                        # [NEW] shape (composition root)
tests/
  test_send_notification.py      # [NEW]
```

Put an empty `__init__.py` in each package folder (`domain/`, `application/`,
`infrastructure/`, `interface/`), exactly like your blog's `routers/__init__.py`.

---

### Step 1 — `domain/notification.py`  **[NEW]**

**Why new:** your blog has no pure business object — it uses the SQLAlchemy model
as the only representation of a post. Here the domain object is plain Python with
the rules baked in, and it imports *nothing* from FastAPI or SQLAlchemy. That
independence is what lets you unit-test the rules with no database.

```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


class DomainError(Exception):
    """Raised when a business rule is violated."""


@dataclass
class Notification:
    sender_id: int
    recipient_id: int
    message: str
    id: int | None = None
    is_read: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        # Business rules live here, not in the route or the DB.
        if self.sender_id == self.recipient_id:
            raise DomainError("A user cannot notify themselves.")
        if not self.message.strip():
            raise DomainError("Notification message cannot be blank.")
```

`__post_init__` runs automatically right after a dataclass is constructed, so the
rules are enforced the moment a `Notification` exists — you can never hold an
invalid one.

---

### Step 2 — `application/ports.py`  **[NEW]**

**Why new:** this is the "port" — an abstract promise that *something* can save a
notification, without saying how. The use case depends on this, not on
SQLAlchemy. That's the inversion that makes the dependency point inward.

```python
from abc import ABC, abstractmethod

from notifications.domain.notification import Notification


class NotificationRepository(ABC):
    @abstractmethod
    async def add(self, notification: Notification) -> Notification:
        """Persist a notification and return it with its id populated."""
        ...
```

`ABC` + `@abstractmethod` means you can't instantiate this directly — only a
concrete subclass that implements `add`. Python enforces that at runtime.

---

### Step 3 — `application/send_notification.py`  **[NEW]**

**Why new:** this is the body of a handler like `create_post`, lifted out of the
route into its own object. It orchestrates the domain and the repository, and it
receives the repository through its constructor (it never imports the concrete
one). This is the file the unit test exercises.

```python
from dataclasses import dataclass

from notifications.application.ports import NotificationRepository
from notifications.domain.notification import Notification


@dataclass
class SendNotification:
    repository: NotificationRepository  # the interface, not the concrete repo

    async def execute(
        self,
        sender_id: int,
        recipient_id: int,
        message: str,
    ) -> Notification:
        notification = Notification(          # rules enforced here (Step 1)
            sender_id=sender_id,
            recipient_id=recipient_id,
            message=message,
        )
        return await self.repository.add(notification)
```

---

### Step 4 — `infrastructure/database.py`  **[ADAPTED]**

**Why adapted:** this is your blog's `database.py` almost verbatim — same engine,
same `async_sessionmaker`, same `get_db`. Only the `config` import path changes.

```python
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from notifications.config import settings

engine = create_async_engine(settings.database_url)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
```

(Your `config.py` carries over unchanged — copy it and keep only the settings
this app needs: `database_url` to start.)

---

### Step 5 — `infrastructure/models.py`  **[ADAPTED]**

**Why adapted:** same `Mapped` / `mapped_column` style as your blog's `models.py`.
The difference is conceptual: this ORM class is now clearly an *infrastructure
detail*, separate from the domain `Notification`. Same data, two classes, on
purpose.

```python
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from notifications.infrastructure.database import Base


class NotificationModel(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    sender_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    recipient_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    is_read: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC),
    )
```

---

### Step 6 — `infrastructure/repository.py`  **[NEW]**

**Why new:** this is where the `db.add / commit / refresh` lines from
`create_post` actually live now — implementing the port from Step 2. The critical
part is `_to_domain`: it maps the ORM row back to a domain object so the ORM class
**never leaves this file**. This is the mapping that feels tedious; do not skip it.

```python
from sqlalchemy.ext.asyncio import AsyncSession

from notifications.application.ports import NotificationRepository
from notifications.domain.notification import Notification
from notifications.infrastructure.models import NotificationModel


class SQLAlchemyNotificationRepository(NotificationRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, notification: Notification) -> Notification:
        row = NotificationModel(                 # domain -> ORM
            sender_id=notification.sender_id,
            recipient_id=notification.recipient_id,
            message=notification.message,
            is_read=notification.is_read,
            created_at=notification.created_at,
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return self._to_domain(row)              # ORM -> domain

    @staticmethod
    def _to_domain(row: NotificationModel) -> Notification:
        return Notification(
            id=row.id,
            sender_id=row.sender_id,
            recipient_id=row.recipient_id,
            message=row.message,
            is_read=row.is_read,
            created_at=row.created_at,
        )
```

---

### Step 7 — `interface/schemas.py`  **[ADAPTED]**

**Why adapted:** same Pydantic v2 style as your blog's `schemas.py`, including
`ConfigDict(from_attributes=True)`. `from_attributes` reads plain attributes, so
it serializes your **domain** `Notification` dataclass directly — no ORM object
involved.

```python
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SendNotificationRequest(BaseModel):
    sender_id: int
    recipient_id: int
    message: str = Field(min_length=1, max_length=500)


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sender_id: int
    recipient_id: int
    message: str
    is_read: bool
    created_at: datetime
```

---

### Step 8 — `interface/routes.py`  **[NEW]** shape

**Why new shape:** compare this to `create_post`. The handler no longer touches
the database. It parses the request, calls the use case, and maps the result to a
response schema. The `get_send_notification` function is the small "composition"
that wires the concrete repository into the use case — the equivalent of your
`Depends(get_db)`, one level up.

```python
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from notifications.application.send_notification import SendNotification
from notifications.domain.notification import DomainError
from notifications.infrastructure.database import get_db
from notifications.infrastructure.repository import SQLAlchemyNotificationRepository
from notifications.interface.schemas import (
    NotificationResponse,
    SendNotificationRequest,
)

router = APIRouter()


def get_send_notification(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SendNotification:
    repository = SQLAlchemyNotificationRepository(db)   # concrete plugs in here
    return SendNotification(repository=repository)


@router.post(
    "",
    response_model=NotificationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def send_notification(
    payload: SendNotificationRequest,
    use_case: Annotated[SendNotification, Depends(get_send_notification)],
) -> NotificationResponse:
    try:
        notification = await use_case.execute(
            sender_id=payload.sender_id,
            recipient_id=payload.recipient_id,
            message=payload.message,
        )
    except DomainError as err:                           # domain rule -> HTTP 422
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(err),
        ) from err
    return NotificationResponse.model_validate(notification)
```

---

### Step 9 — `main.py`  **[NEW]** shape

**Why new shape:** same `lifespan` + `create_all` pattern as your blog's
`main.py`, but this is the app's **composition root** — the one place that knows
about all layers and wires them together. Note the `models` import: it must run
before `create_all` so the table is registered on `Base.metadata` (your blog does
the same with `import models`).

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI

from notifications.infrastructure import models  # noqa: F401  (registers the table)
from notifications.infrastructure.database import Base, engine
from notifications.interface.routes import router as notifications_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(lifespan=lifespan)
app.include_router(
    notifications_router,
    prefix="/api/notifications",
    tags=["notifications"],
)
```

Run it the same way as the blog (`uv run fastapi dev`), open `/docs`, and the
POST endpoint is there to try in Swagger.

---

### Step 10 — `tests/test_send_notification.py`  **[NEW]**

**Why new — and why it's the point:** this test runs the use case with a **fake
in-memory repository**, no database at all. It's fast, and it proves the business
rules independently of SQLAlchemy. This is the payoff of everything above; if it
feels good to write, the architecture earned its keep.

Add the dev dependency first: `uv add --dev pytest pytest-asyncio`. Then in
`pyproject.toml` add:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

```python
import pytest

from notifications.application.ports import NotificationRepository
from notifications.application.send_notification import SendNotification
from notifications.domain.notification import DomainError, Notification


class FakeNotificationRepository(NotificationRepository):
    def __init__(self) -> None:
        self.saved: list[Notification] = []
        self._next_id = 1

    async def add(self, notification: Notification) -> Notification:
        notification.id = self._next_id
        self._next_id += 1
        self.saved.append(notification)
        return notification


async def test_send_notification_persists_and_returns_it():
    repo = FakeNotificationRepository()
    use_case = SendNotification(repository=repo)

    result = await use_case.execute(sender_id=1, recipient_id=2, message="Hello")

    assert result.id == 1
    assert len(repo.saved) == 1
    assert repo.saved[0].message == "Hello"


async def test_cannot_notify_yourself():
    repo = FakeNotificationRepository()
    use_case = SendNotification(repository=repo)

    with pytest.raises(DomainError):
        await use_case.execute(sender_id=1, recipient_id=1, message="Hi")

    assert repo.saved == []   # nothing was saved because the rule fired first
```

Run: `uv run pytest`. Both green = the slice is done.

---

## 5. The two ways you'll verify this slice

They prove different things — do both:
- **`uv run pytest`** — proves the *logic* (the rules), with no database. This is
  what the architecture buys you.
- **Swagger `/docs`** — proves the *wiring* (route → use case → repo → DB row),
  end to end. Needs the table, which `create_all` builds on startup.

Passing one does not imply the other.

---

## 6. Using Claude Code as the checker (not the explainer)

Point the VS Code extension at both folders so it can compare against your real
blog, then give it a checking role instead of an explaining one:

> I'm building a notifications app in clean architecture, typing it myself from a
> reference doc. My blog `fastapi_blog` is added as read-only reference for the
> async SQLAlchemy, settings, and JWT patterns ONLY — do not copy its flat route
> structure. As I paste each file, check it against the reference intent: verify
> the dependency rule (no FastAPI/SQLAlchemy imports in domain or application),
> and that the ORM model never leaves infrastructure. Point out violations. Do
> not write the code for me unless I ask.

Add the blog with `/add-dir "C:\Users\Asus\Documents\MEGA\MEGA downloads\python\fastapi_blog"`.

That keeps the explanation here (this doc), and makes Claude Code the second pair
of eyes in your editor — which removes the mismatch that was confusing you.
