# AI Finance Operations Platform

# Migration and ORM Specification

## Version 2.6

## Filename: 16_Migration_and_ORM_Specification.md

## Prepared For: mmlogistix

## Date: 19 May 2026

---

# Companion Documents

| Document | Filename |
|----------|----------|
| Project Overview | 00_Project_Overview.md |
| Business Requirements | 01_Business_Requirement_Document.md |
| Technical Architecture | 02_Technical_Architecture.md |
| Cursor Development Brief | 03_Cursor_Development_Brief.md |
| Hermes Integration Specification | 04_Hermes_Integration_Spec.md |
| API Specification | 05_API_Specification.md |
| Database Schema | 06_Database_Schema_Design.md |
| AI Runtime Sequences | 07_AI_Runtime_Sequence_Diagrams.md |
| Workflow State Machine | 08_Workflow_State_Machine.md |
| Event Model | 09_Event_Model_Specification.md |
| Policy Engine | 10_Policy_Engine_Specification.md |
| Deployment Runbook | 11_Deployment_Operations_Runbook.md |
| Testing Strategy | 12_Testing_and_UAT_Strategy.md |
| Security & Compliance Specification | 13_Security_and_Compliance_Specification.md |
| Environment & Configuration Reference | 14_Environment_and_Configuration_Reference.md |
| Approval UI Specification | 15_Approval_UI_Specification.md |
| Migration and ORM Specification | 16_Migration_and_ORM_Specification.md |
| Worker Specifications | 17_Worker_Specifications.md |
| Notification Service Specification | 18_Notification_Service_Specification.md |
| Expense Worker Specification | 19_Expense_Worker_Specification.md |
| Git Workflow and Prompt Management | 20_Git_Workflow_and_Prompt_Management.md |
| OpenAPI Contract | 21_openapi.yaml |

---

# Table of Contents

1. [Purpose and Conflict Resolution](#1-purpose-and-conflict-resolution)
2. [Tooling and File Format Decision](#2-tooling-and-file-format-decision)
3. [Repository Structure](#3-repository-structure)
4. [Alembic Configuration](#4-alembic-configuration)
5. [SQLAlchemy Base and Mixins](#5-sqlalchemy-base-and-mixins)
6. [Migration Authoring Rules](#6-migration-authoring-rules)
7. [Phase 2 ORM Models](#7-phase-2-orm-models)
8. [Phase 2 Migrations — Complete Files](#8-phase-2-migrations--complete-files)
9. [Shared Database Utilities](#9-shared-database-utilities)
10. [Migration Naming and Ordering Reference](#10-migration-naming-and-ordering-reference)
11. [Common Patterns and Gotchas](#11-common-patterns-and-gotchas)

---

# 1. Purpose and Conflict Resolution

## 1.1 The Conflict

Two documents in this suite reference migration files with inconsistent formats:

- **`00_Project_Overview.md` §5.1** lists phase migration artefacts with `.sql` extensions:
  `002_auth_rbac.sql`, `003_mail_gateway.sql`, `004_workflow_policy.sql`, etc.

- **`06_Database_Schema_Design.md` §17.2** and **`03_Cursor_Development_Brief.md` §13.2** both show `.py` Alembic migration files with `upgrade()` / `downgrade()` functions.

## 1.2 Resolution

**Migrations are `.py` Alembic files. The `.sql` labels in `00_Project_Overview.md` §5.1 are logical phase identifiers, not literal filenames.** They describe the content scope of each phase's migrations, not the file format.

The authoritative format is the Alembic `.py` pattern shown in `06` §17.2. This document supersedes the `.sql` labels in `00` §5.1 for the purpose of file creation. When the roadmap says `002_auth_rbac.sql`, the developer produces the six `.py` migration files listed in `06` §18.4 for Phase 2.

## 1.3 Why Alembic `.py` (not raw `.sql`)

| Concern | Alembic `.py` | Raw `.sql` |
|---------|---------------|------------|
| Reversible downgrade | ✅ Built-in `downgrade()` | ❌ Must write manually per file |
| Cross-database dialect | ✅ SQLAlchemy abstracts types | ❌ PostgreSQL-only syntax |
| Migration state tracking | ✅ `alembic_version` table automatic | ❌ Manual bookkeeping |
| CI/CD integration | ✅ `alembic upgrade head` in pipeline | ❌ Custom script required |
| Partial upgrades / head detection | ✅ Revision DAG | ❌ Not available |
| Python logic in migrations | ✅ Can run Python for data migrations | ❌ Cannot |

Raw `.sql` files may still be used as **reference** (e.g., the DDL blocks in `06_Database_Schema_Design.md`), but they are documentation, not migration artefacts.

## 1.4 Document Scope — Phase 2 Reference Implementation

**This document provides complete, production-ready migration files and ORM models for Phase 2 only** (Auth & RBAC — migrations 001–006). This is intentional: Phase 2 is the most foundational phase, establishes all shared patterns, and is the highest-value phase to specify completely.

For Phases 3–11, developers apply the same patterns to the DDL defined in `06_Database_Schema_Design.md`:

| What this document provides | What the developer derives |
|-----------------------------|---------------------------|
| §4 `alembic.ini` + `env.py` config | Reuse as-is for all phases |
| §5 `Base`, `TimestampMixin`, type aliases | Import into every ORM model |
| §6 Migration authoring rules | Apply to every migration file |
| §7 Phase 2 ORM models (Role, Permission, RolePermission, User, RefreshToken) | Pattern for all subsequent models |
| §8 Six complete Phase 2 migration files | Pattern for all subsequent migrations |
| §9 Shared DB utilities (session factory, health check) | Reuse as-is |
| §10 Migration naming/ordering reference table | Canonical mapping for all phases |
| §11 Common patterns and gotchas | Apply throughout |

The DDL for Phases 3–11 is authoritative in `06_Database_Schema_Design.md`. The ORM models for Phases 3–11 follow the `TimestampMixin` + `DeclarativeBase` pattern shown in §7. The migration structure follows the template in §8 (full `upgrade()` / `downgrade()` with enum handling, FK creation, trigger attachment, and index creation).

**Phase-specific DDL source reference:**

| Phase | Tables | DDL Source |
|-------|--------|-----------|
| 2 | roles, permissions, role_permissions, users, refresh_tokens | §7–§8 (this document) |
| 3 | emails, email_attachments, mail_gateway_config | `06` §7 |
| 4 | counterparty, cases, case_*, workflow_*, policies, policy_*, approvals, approval_* | `06` §4–§6, §9 |
| 5 | queue_messages + seed | `06` §8, §19 |
| 6–7 | purchase_orders | `06` §13a |
| 8 | coa_accounts, journal_entries, journal_entry_lines, reconciliation_* | `06` §10–§12 |
| 9 | notification_templates, user_notification_preferences, notifications | `06` §3.6–§3.8 |
| 10 | audit_logs, system_settings | `06` §13 |
| 11 | expense_claims, expense_line_items, expense_policies | `19` §3 |

---

# 2. Tooling and File Format Decision

## 2.1 Stack

| Component | Choice | Version |
|-----------|--------|---------|
| ORM | SQLAlchemy | `>=2.0` (declarative, typed) |
| Migrations | Alembic | `>=1.13` |
| Async driver | asyncpg | `>=0.29` |
| Sync driver (Alembic) | psycopg2 | `>=2.9` |
| Settings | pydantic-settings | `>=2.0` |
| Managed database | Supabase Cloud | PostgreSQL 17.6.1.121 |

Alembic uses a **synchronous** psycopg2 connection for migration execution (standard practice — Alembic does not support asyncpg natively). The application itself uses asyncpg via SQLAlchemy's async engine. Both share the same `FINANCE_DATABASE_URL`; Alembic strips the `+asyncpg` driver prefix internally (see §4.2).

## 2.2 Migration File Naming

```
migrations/versions/{YYYYMMDD}_{HHMMSS}_{NNN}_{description}.py
```

| Segment | Example | Rules |
|---------|---------|-------|
| `YYYYMMDD_HHMMSS` | `20260510_143200` | Timestamp of file creation — ensures chronological order in `ls` |
| `NNN` | `001`, `002` | Three-digit phase-ordered sequence — ties filenames to `06` §18.4 |
| `description` | `create_roles_table` | Snake-case, imperative verb, specific |

**Full example:**
```
migrations/versions/20260510_143200_001_create_roles_table.py
```

The `NNN` prefix is the developer's primary ordering reference. The timestamp ensures uniqueness in automated generation. Alembic's internal ordering uses the `down_revision` chain, not the filename — but filenames that sort correctly make git history and `ls -la` readable.

> **Exception — `035b` suffix:** Migration `035b_create_notifications_table.py` is a deliberate exception to the three-digit `NNN` convention. It inserts a Phase 9 migration between `035` and `036` without renumbering subsequent migrations. When creating this file, do **not** use `alembic revision --autogenerate` (the generated name will not carry the `b` suffix). Instead, create the file manually, set `down_revision = "035_or_actual_revision_id_of_035"` explicitly, and name the file `035b_create_notifications_table.py`. No other migration uses a lettered suffix — this is a one-off to preserve the existing `036` revision chain. See §10 for the full Phase 9 migration sequence.

---

## 2.3 Supabase Cloud — Connection and CLI

This project uses **Supabase Cloud** (not self-hosted). The database is fully managed infrastructure.

| Detail | Value |
|--------|-------|
| Project ref | `ehsoeyfopazodvmpkkpy` |
| Project URL | `https://ehsoeyfopazodvmpkkpy.supabase.co` |
| Direct connection (Alembic / psycopg2) | `postgresql://postgres:[PASSWORD]@db.ehsoeyfopazodvmpkkpy.supabase.co:5432/postgres` |
| Async connection (SQLAlchemy / asyncpg) | `postgresql+asyncpg://postgres:[PASSWORD]@db.ehsoeyfopazodvmpkkpy.supabase.co:5432/postgres` |
| PostgreSQL version | 17.6.1.121 |
| PostgREST version | 14.5 |
| GoTrue (Auth) version | 2.189.0 |
| Storage bucket | `finance-attachments` (private) |

**Alembic uses the direct connection string.** The `FINANCE_DATABASE_URL` env var uses `postgresql+asyncpg://...` for application runtime. Alembic's `env.py` strips `+asyncpg` and substitutes `+psycopg2` for synchronous migration execution — this is handled automatically in §4.2.

**CLI link (run once per developer machine):**

```bash
# Install Supabase CLI
npm install -g supabase

# Authenticate
supabase login

# Initialise local config (only if no supabase/ dir exists in repo root)
supabase init

# Link to the cloud project
supabase link --project-ref ehsoeyfopazodvmpkkpy
```

The Supabase CLI is used for storage bucket management and dashboard inspection only. **Migrations are exclusively managed by Alembic** — never via the Supabase dashboard SQL editor or `supabase db push`.

> **Anon key:** Not required for this platform. All database access uses the direct asyncpg connection string or the service role key for Supabase Storage operations. The application is server-side only; the anon key is reserved for any future client-side use and must not be embedded in server configuration.

---

# 3. Repository Structure

```
finance-platform/
├── alembic.ini                          # Alembic config — points to migrations/
├── migrations/
│   ├── env.py                           # Alembic environment — async engine setup
│   ├── script.py.mako                   # Template for generated migration files
│   └── versions/
│       ├── 20260510_143200_001_create_roles_table.py
│       ├── 20260510_143300_002_create_permissions_table.py
│       ├── 20260510_143400_003_create_role_permissions_table.py
│       ├── 20260510_143500_004_create_users_table.py
│       ├── 20260510_143600_005_create_refresh_tokens_table.py
│       └── 20260510_143700_006_seed_roles_and_permissions.py
│       └── ... (subsequent phases)
│
└── app/
    └── models/
        ├── base.py                      # DeclarativeBase, TimestampMixin
        ├── rbac.py                      # Role, Permission, RolePermission
        ├── user.py                      # User, RefreshToken
        ├── case.py                      # Case, CaseTimeline, etc. (Phase 4)
        └── ...
```

---

# 4. Alembic Configuration

## 4.1 alembic.ini

```ini
# alembic.ini
[alembic]
script_location = migrations
prepend_sys_path = .
version_path_separator = os

# Use %(here)s to make paths relative to alembic.ini location
file_template = %%(year)d%%(month)02d%%(day)02d_%%(hour)02d%%(minute)02d%%(second)02d_%(slug)s

# Do not set sqlalchemy.url here — it is set programmatically in env.py
# from the FINANCE_DATABASE_URL environment variable.

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

## 4.2 migrations/env.py

```python
# migrations/env.py
"""Alembic environment — synchronous runner with settings-driven URL."""

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Import all models so Alembic can detect schema changes with --autogenerate
from app.models.base import Base  # noqa: F401
from app.models.rbac import Role, Permission, RolePermission  # noqa: F401
from app.models.user import User, RefreshToken  # noqa: F401
# Phase 3+ models imported here as they are created:
# from app.models.email import Email, EmailAttachment  # noqa: F401
# from app.models.case import Case, CaseTimeline, ...   # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    """
    Read FINANCE_DATABASE_URL from environment and convert asyncpg driver to
    psycopg2 for Alembic's synchronous runner.

    FINANCE_DATABASE_URL = postgresql+asyncpg://postgres:[PASSWORD]@db.ehsoeyfopazodvmpkkpy.supabase.co:5432/postgres
    Alembic needs:         postgresql+psycopg2://postgres:[PASSWORD]@db.ehsoeyfopazodvmpkkpy.supabase.co:5432/postgres
    """
    url = os.environ.get("FINANCE_DATABASE_URL", "")
    if not url:
        raise RuntimeError(
            "FINANCE_DATABASE_URL environment variable is not set. "
            "Set it in your .env file or shell before running alembic."
        )
    return url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")


def run_migrations_offline() -> None:
    """Run migrations without a live DB connection (emit SQL to stdout)."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live DB connection."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

## 4.3 Common Alembic Commands

```bash
# Apply all pending migrations to the database
alembic upgrade head

# Roll back the most recent migration
alembic downgrade -1

# Roll back to a specific revision
alembic downgrade abc12345

# Show current revision applied to the database
alembic current

# Show full migration history
alembic history --verbose

# Generate a new migration by comparing ORM models to live DB (autogenerate)
# Always review autogenerated output — it misses some things (triggers, RLS, GIN indexes)
alembic revision --autogenerate -m "add_two_factor_secret_to_users"

# Create a blank migration (preferred for complex migrations)
alembic revision -m "create_users_table"

# Check for unapplied migrations (useful in CI health check)
alembic check
```

---

# 5. SQLAlchemy Base and Mixins

## 5.1 app/models/base.py

```python
# app/models/base.py
"""
Shared SQLAlchemy declarative base and reusable column mixins.
Import Base into every ORM model file and use mixins to enforce schema
conventions from 06_Database_Schema_Design.md §1.
"""

import uuid
from datetime import datetime
from typing import Annotated

from sqlalchemy import DateTime, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


# ── Annotated type aliases ────────────────────────────────────────────────────
# These make column declarations concise and consistent across all models.

# UUID primary key — always server-generated, never set by Python
pk_uuid = Annotated[
    uuid.UUID,
    mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        sort_order=-10,                     # always first in column list
    ),
]

# Timestamp with timezone — server default NOW()
ts_now = Annotated[
    datetime,
    mapped_column(
        DateTime(timezone=True),
        server_default=text("NOW()"),
        nullable=False,
    ),
]

# Optional timestamp (nullable) — for fields like last_login_at, completed_at
ts_optional = Annotated[
    datetime | None,
    mapped_column(DateTime(timezone=True), nullable=True),
]


class Base(DeclarativeBase):
    """
    Project-wide declarative base.

    All ORM models must inherit from this class.
    Alembic's env.py imports Base.metadata for --autogenerate.
    """
    pass


class TimestampMixin:
    """
    Adds created_at and updated_at to any model.
    updated_at is maintained by the auto_update_timestamp PostgreSQL trigger
    (created in migration 001 — see §8.1).
    The ORM-level onupdate is a belt-and-suspenders fallback for direct
    Python ORM updates that bypass the DB trigger.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("NOW()"),
        nullable=False,
        sort_order=98,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("NOW()"),
        onupdate=datetime.utcnow,
        nullable=False,
        sort_order=99,
    )


class SoftDeleteMixin:
    """
    Adds deleted_at for soft-delete pattern (06_Database_Schema_Design §1.4).
    Repositories must add `WHERE deleted_at IS NULL` via a default filter.
    """

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        sort_order=100,
    )
```

---

# 6. Migration Authoring Rules

These rules expand on `06_Database_Schema_Design.md` §17.1 with concrete implementation guidance.

1. **One logical change per migration.** "Create table + indexes + seed data" for the same table is acceptable in one file (it is one logical unit). Combining two unrelated tables is not.

2. **Naming:** `YYYYMMDD_HHMMSS_NNN_description.py` where `NNN` matches the sequence in §10. Exception: `035b` uses a lettered suffix — see §2.2 for the manual creation procedure.

3. **Always write `downgrade()`** that exactly reverses `upgrade()`. Drop objects in reverse order of creation. If a migration is truly irreversible (e.g. dropping a column with data), add:
   ```python
   from alembic.util import IrreversibleError
   def downgrade() -> None:
       raise IrreversibleError("This migration cannot be reversed — data loss.")
   ```

4. **Use `op.create_table()` for new tables**, not `op.execute("CREATE TABLE ...")`. The former is dialect-aware and shows up in `--autogenerate` diffs.

5. **Use `op.execute()` for PostgreSQL-specific DDL** that has no SQLAlchemy abstraction: triggers, ENUM types, RLS policies, GIN indexes with `to_tsvector`, `CREATE INDEX CONCURRENTLY`.

6. **ENUM types:** Create with `op.execute("CREATE TYPE ...")` before `op.create_table()`. Drop with `op.execute("DROP TYPE IF EXISTS ...")` after `op.drop_table()` in `downgrade()`.

7. **Seed data in migrations:** Insert system roles and permissions in `006_seed_roles_and_permissions.py`. Use `op.bulk_insert()` for multiple rows — it is faster than repeated `op.execute()` and participates in the migration transaction.

8. **GIN indexes** (`to_tsvector`, array operators) must use `op.execute()` — SQLAlchemy's `create_index()` does not support the full GIN syntax.

9. **Test every migration locally** with `alembic upgrade head` on a clean database, then `alembic downgrade base` to verify `downgrade()`. Both must succeed without errors before committing.

10. **Never modify a committed migration.** If a committed migration has a bug, create a new migration to fix it. Modifying committed migrations breaks the revision chain for anyone who has already applied them.

---

# 7. Phase 2 ORM Models

## 7.1 app/models/rbac.py

```python
# app/models/rbac.py
"""
ORM models for Phase 2 Auth & RBAC.
Tables: roles, permissions, role_permissions
Schema source: 06_Database_Schema_Design.md §3.2, §3.3, §3.4
"""

import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, pk_uuid


class Role(Base, TimestampMixin):
    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(pk_uuid)
    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Relationships
    users: Mapped[list["User"]] = relationship("User", back_populates="role")
    role_permissions: Mapped[list["RolePermission"]] = relationship(
        "RolePermission", back_populates="role", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Role {self.name!r}>"


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[uuid.UUID] = mapped_column(pk_uuid)
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # permissions has no updated_at — it is an immutable catalog after seeding
    from sqlalchemy import DateTime, text
    from datetime import datetime
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False
    )

    # Relationships
    role_permissions: Mapped[list["RolePermission"]] = relationship(
        "RolePermission", back_populates="permission", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Permission {self.code!r}>"


class RolePermission(Base):
    __tablename__ = "role_permissions"
    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="role_permissions_pkey"),
    )

    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    permission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    from sqlalchemy import DateTime, text
    from datetime import datetime
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False
    )

    # Relationships
    role: Mapped["Role"] = relationship("Role", back_populates="role_permissions")
    permission: Mapped["Permission"] = relationship(
        "Permission", back_populates="role_permissions"
    )
```

## 7.2 app/models/user.py

```python
# app/models/user.py
"""
ORM models for Phase 2 Auth & RBAC.
Tables: users, refresh_tokens, password_history
Schema source: 06_Database_Schema_Design.md §3.1, §3.5, §3.6
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, CheckConstraint, ForeignKey, Integer,
    String, Text, DateTime, text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, pk_uuid


class User(Base, TimestampMixin):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'inactive', 'locked')",
            name="users_status_check",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(pk_uuid)
    username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("roles.id"),
        nullable=False,
    )
    department: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="active"
    )
    two_factor_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    two_factor_secret: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )  # Encrypted TOTP secret — see 13_Security §5.2
    failed_login_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    role: Mapped["Role"] = relationship("Role", back_populates="users")
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        "RefreshToken", back_populates="user", cascade="all, delete-orphan"
    )
    password_history: Mapped[list["PasswordHistory"]] = relationship(
        "PasswordHistory", back_populates="user", cascade="all, delete-orphan",
        order_by="PasswordHistory.created_at.desc()",
    )

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    @property
    def is_locked(self) -> bool:
        return self.status == "locked"

    def __repr__(self) -> str:
        return f"<User {self.username!r} status={self.status!r}>"


class RefreshToken(Base, TimestampMixin):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(pk_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(
        String(255), nullable=False
    )  # SHA-256 of the raw token — never store the raw token
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="refresh_tokens")

    @property
    def is_valid(self) -> bool:
        from datetime import timezone
        return (
            self.revoked_at is None
            and self.expires_at > datetime.now(tz=timezone.utc)
        )

    def __repr__(self) -> str:
        return f"<RefreshToken user_id={self.user_id!r} valid={self.is_valid}>"


class PasswordHistory(Base):
    __tablename__ = "password_history"

    id: Mapped[uuid.UUID] = mapped_column(pk_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    password_hash: Mapped[str] = mapped_column(
        String(255), nullable=False
    )  # Argon2id hash of the historical password — never store plaintext
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("NOW()"),
        nullable=False,
    )
    # No updated_at — this table is append-only; the auto_update_timestamp
    # trigger is NOT applied. See 06_Database_Schema_Design.md §3.6.

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="password_history")

    def __repr__(self) -> str:
        return f"<PasswordHistory user_id={self.user_id!r} created_at={self.created_at!r}>"
```

---

# 8. Phase 2 Migrations — Complete Files

These are the six complete migrations for Phase 2 (Auth & RBAC), corresponding to entries `001`–`006` in `06_Database_Schema_Design.md` §18.4. They are production-ready: every column matches the DDL in `06`, every index is present, `downgrade()` is implemented, and the seed data matches `06` §18.1–18.3.

The revision IDs below use short readable strings. In practice, run `alembic revision` to generate cryptographic revision IDs, then paste the `upgrade()` / `downgrade()` body into the generated file.

---

## 8.1 001 — Create roles table

**File:** `migrations/versions/20260510_143200_001_create_roles_table.py`

```python
"""create_roles_table

Revision ID: 20260510_001
Revises:
Create Date: 2026-05-10 14:32:00.000000

Creates the roles table and the auto_update_timestamp trigger function.
The trigger function is created here once; subsequent migrations apply it
to each new table with an updated_at column.

Schema source: 06_Database_Schema_Design.md §3.2
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260510_001"
down_revision = None          # first migration — no predecessor
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. Create the shared auto_update_timestamp trigger function ──────────
    # Created once here; reused by all subsequent tables with updated_at.
    op.execute("""
        CREATE OR REPLACE FUNCTION auto_update_timestamp()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # ── 2. Create roles table ────────────────────────────────────────────────
    op.create_table(
        "roles",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "is_system",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.UniqueConstraint("name", name="roles_name_key"),
    )

    # ── 3. Indexes ───────────────────────────────────────────────────────────
    op.create_index("roles_name_idx", "roles", ["name"])

    # ── 4. updated_at trigger ────────────────────────────────────────────────
    op.execute("""
        CREATE TRIGGER roles_updated_at
            BEFORE UPDATE ON roles
            FOR EACH ROW EXECUTE FUNCTION auto_update_timestamp();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS roles_updated_at ON roles;")
    op.drop_index("roles_name_idx", table_name="roles")
    op.drop_table("roles")
    # Drop the shared trigger function only on full downgrade to base.
    # If other tables still use it, leave it in place.
    # Safe to drop here only because roles is the first (base) migration.
    op.execute("DROP FUNCTION IF EXISTS auto_update_timestamp();")
```

---

## 8.2 002 — Create permissions table

**File:** `migrations/versions/20260510_143300_002_create_permissions_table.py`

```python
"""create_permissions_table

Revision ID: 20260510_002
Revises: 20260510_001
Create Date: 2026-05-10 14:33:00.000000

Schema source: 06_Database_Schema_Design.md §3.3
Note: permissions has no updated_at — it is a seeded catalog, not updated at runtime.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260510_002"
down_revision = "20260510_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "permissions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.UniqueConstraint("code", name="permissions_code_key"),
    )

    op.create_index("permissions_category_idx", "permissions", ["category"])


def downgrade() -> None:
    op.drop_index("permissions_category_idx", table_name="permissions")
    op.drop_table("permissions")
```

---

## 8.3 003 — Create role_permissions table

**File:** `migrations/versions/20260510_143400_003_create_role_permissions_table.py`

```python
"""create_role_permissions_table

Revision ID: 20260510_003
Revises: 20260510_002
Create Date: 2026-05-10 14:34:00.000000

Schema source: 06_Database_Schema_Design.md §3.4
Junction table — composite primary key (role_id, permission_id).
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260510_003"
down_revision = "20260510_002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "role_permissions",
        sa.Column(
            "role_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("roles.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "permission_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("permissions.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )

    # Supports fast lookup: "what roles have permission X?"
    op.create_index(
        "role_permissions_permission_id_idx",
        "role_permissions",
        ["permission_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "role_permissions_permission_id_idx", table_name="role_permissions"
    )
    op.drop_table("role_permissions")
```

---

## 8.4 004 — Create users table

**File:** `migrations/versions/20260510_143500_004_create_users_table.py`

```python
"""create_users_table

Revision ID: 20260510_004
Revises: 20260510_003
Create Date: 2026-05-10 14:35:00.000000

Schema source: 06_Database_Schema_Design.md §3.1

Notes:
- two_factor_secret stores an encrypted TOTP secret (AES-256 at application
  layer per 13_Security_and_Compliance_Specification.md §5.2).
  The column is VARCHAR(255) to accommodate encrypted ciphertext, not the
  raw 32-char base32 secret.
- password_hash stores Argon2id output (~95 chars). VARCHAR(255) is sufficient.
- status CHECK constraint enforces the three valid states.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260510_004"
down_revision = "20260510_003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column(
            "role_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("roles.id"),
            nullable=False,
        ),
        sa.Column("department", sa.String(100), nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "two_factor_enabled",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("two_factor_secret", sa.String(255), nullable=True),
        sa.Column(
            "failed_login_attempts",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.UniqueConstraint("username", name="users_username_key"),
        sa.UniqueConstraint("email", name="users_email_key"),
        sa.CheckConstraint(
            "status IN ('active', 'inactive', 'locked')",
            name="users_status_check",
        ),
    )

    # ── Indexes ──────────────────────────────────────────────────────────────
    op.create_index("users_username_idx", "users", ["username"])
    op.create_index("users_role_id_idx", "users", ["role_id"])
    op.create_index("users_email_idx", "users", ["email"])

    # Partial index — only index active users (frequent query pattern)
    op.execute("""
        CREATE INDEX users_status_idx ON users(status)
        WHERE status = 'active';
    """)

    # ── updated_at trigger ───────────────────────────────────────────────────
    op.execute("""
        CREATE TRIGGER users_updated_at
            BEFORE UPDATE ON users
            FOR EACH ROW EXECUTE FUNCTION auto_update_timestamp();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS users_updated_at ON users;")
    op.execute("DROP INDEX IF EXISTS users_status_idx;")
    op.drop_index("users_email_idx", table_name="users")
    op.drop_index("users_role_id_idx", table_name="users")
    op.drop_index("users_username_idx", table_name="users")
    op.drop_table("users")
```

---

## 8.5 005 — Create refresh_tokens table

**File:** `migrations/versions/20260510_143600_005_create_refresh_tokens_table.py`

```python
"""create_refresh_tokens_table

Revision ID: 20260510_005
Revises: 20260510_004
Create Date: 2026-05-10 14:36:00.000000

Schema source: 06_Database_Schema_Design.md §3.5

Stores hashed JWT refresh tokens. Raw tokens are never persisted.
token_hash = SHA-256(raw_token) as hex string (64 chars).
expires_at is set to NOW() + 7 days at insert time (application logic).
revoked_at is set on logout or security event.

The partial index on expires_at (WHERE revoked_at IS NULL) supports
efficient purge of expired-but-not-yet-revoked tokens.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260510_005"
down_revision = "20260510_004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "refresh_tokens",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )

    # ── Indexes ──────────────────────────────────────────────────────────────
    op.create_index("refresh_tokens_user_id_idx", "refresh_tokens", ["user_id"])
    op.create_index(
        "refresh_tokens_token_hash_idx", "refresh_tokens", ["token_hash"]
    )

    # Partial index: fast expiry checks on non-revoked tokens only
    op.execute("""
        CREATE INDEX refresh_tokens_expires_at_idx ON refresh_tokens(expires_at)
        WHERE revoked_at IS NULL;
    """)

    # ── updated_at trigger ───────────────────────────────────────────────────
    op.execute("""
        CREATE TRIGGER refresh_tokens_updated_at
            BEFORE UPDATE ON refresh_tokens
            FOR EACH ROW EXECUTE FUNCTION auto_update_timestamp();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS refresh_tokens_updated_at ON refresh_tokens;")
    op.execute("DROP INDEX IF EXISTS refresh_tokens_expires_at_idx;")
    op.drop_index("refresh_tokens_token_hash_idx", table_name="refresh_tokens")
    op.drop_index("refresh_tokens_user_id_idx", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
```

---

## 8.6 006 — Seed roles and permissions

**File:** `migrations/versions/20260510_143700_006_seed_roles_and_permissions.py`

```python
"""seed_roles_and_permissions

Revision ID: 20260510_006
Revises: 20260510_005
Create Date: 2026-05-10 14:37:00.000000

Inserts all system roles, the full permissions catalog, and the
role-permission mapping.

Seed data source: 06_Database_Schema_Design.md §18.1, §18.2, §18.3

Role UUIDs are fixed (not gen_random_uuid()) so they can be referenced
reliably in tests, fixtures, and subsequent seed migrations. These UUIDs
must never change after this migration is applied to any environment.

downgrade() removes only the seeded rows. It does NOT drop the tables
(that is handled by migrations 001–005).
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260510_006"
down_revision = "20260510_005"
branch_labels = None
depends_on = None

# ── Fixed role UUIDs (stable across all environments) ────────────────────────
ROLE_PLATFORM_ADMIN  = "00000000-0000-0000-0000-000000000001"  # system@bp0.work
ROLE_CLIENT_ADMIN    = "00000000-0000-0000-0000-000000000008"  # system.<client>@bp0.work
ROLE_CFO             = "00000000-0000-0000-0000-000000000002"
ROLE_FINANCE_MANAGER = "00000000-0000-0000-0000-000000000003"
ROLE_FINANCE_OFFICER = "00000000-0000-0000-0000-000000000004"
ROLE_ACCOUNTS_CLERK  = "00000000-0000-0000-0000-000000000005"
ROLE_AUDITOR         = "00000000-0000-0000-0000-000000000006"
ROLE_GENERAL_MANAGER = "00000000-0000-0000-0000-000000000007"


def upgrade() -> None:
    conn = op.get_bind()

    # ── 1. System roles ───────────────────────────────────────────────────────
    roles_table = sa.table(
        "roles",
        sa.column("id", postgresql.UUID(as_uuid=False)),
        sa.column("name", sa.String),
        sa.column("display_name", sa.String),
        sa.column("description", sa.Text),
        sa.column("is_system", sa.Boolean),
    )

    op.bulk_insert(roles_table, [
        {
            "id": ROLE_PLATFORM_ADMIN,
            "name": "platform_admin",
            "display_name": "Platform Administrator",
            "description": "bp0 operator — platform scope (system@bp0.work)",
            "is_system": True,
        },
        {
            "id": ROLE_CLIENT_ADMIN,
            "name": "client_admin",
            "display_name": "Client System Administrator",
            "description": "Tenant operator — mailboxes, COA, tenant settings (system.<client>@bp0.work)",
            "is_system": True,
        },
        {
            "id": ROLE_CFO,
            "name": "cfo",
            "display_name": "Chief Financial Officer",
            "description": "Tier 3 financial approvals and oversight",
            "is_system": True,
        },
        {
            "id": ROLE_FINANCE_MANAGER,
            "name": "finance_manager",
            "display_name": "Finance Manager",
            "description": "Tier 2 approvals and team management",
            "is_system": True,
        },
        {
            "id": ROLE_FINANCE_OFFICER,
            "name": "finance_officer",
            "display_name": "Finance Officer",
            "description": "Tier 2 approvals and case processing",
            "is_system": True,
        },
        {
            "id": ROLE_ACCOUNTS_CLERK,
            "name": "accounts_clerk",
            "display_name": "Accounts Clerk",
            "description": "Case creation and data entry",
            "is_system": True,
        },
        {
            "id": ROLE_AUDITOR,
            "name": "auditor",
            "display_name": "Auditor",
            "description": "Read-only audit and compliance access",
            "is_system": True,
        },
        {
            "id": ROLE_GENERAL_MANAGER,
            "name": "general_manager",
            "display_name": "General Manager",
            "description": "Operational workflows and escalations — outside the financial approval hierarchy (BRD §8)",
            "is_system": True,
        },
    ])

    # ── 2. Permissions catalog ────────────────────────────────────────────────
    # Insert all 28 permissions (31 after Phase 11 migration 043). IDs are server-generated (gen_random_uuid()).
    op.execute(sa.text("""
        INSERT INTO permissions (code, category, action, description) VALUES
        ('cases:read',            'cases',          'read',    'View cases and case details'),
        ('cases:write',           'cases',          'write',   'Create and update cases'),
        ('cases:delete',          'cases',          'delete',  'Delete cases'),
        ('approvals:read',        'approvals',      'read',    'View approval requests and history'),
        ('approvals:approve',     'approvals',      'approve', 'Approve or reject approval requests'),
        ('approvals:admin',       'approvals',      'admin',   'Override approvals, manage approval rules'),
        ('journal-entries:read',  'journal_entries','read',    'View journal entries'),
        ('journal-entries:write', 'journal_entries','write',   'Create and post journal entries'),
        ('policies:read',         'policies',       'read',    'View accounting and workflow policies'),
        ('policies:write',        'policies',       'write',   'Create and update policies'),
        ('queues:read',           'queues',         'read',    'View queue status and messages'),
        ('queues:admin',          'queues',         'admin',   'Manage queue messages, retry, purge'),
        ('reconciliation:read',   'reconciliation', 'read',    'View reconciliation data'),
        ('reconciliation:write',  'reconciliation', 'write',   'Perform reconciliations, match/unmatch'),
        ('audit-logs:read',       'audit_logs',     'read',    'View audit logs'),
        ('users:read',            'users',          'read',    'View users'),
        ('users:write',           'users',          'write',   'Create and update users'),
        ('users:admin',           'users',          'admin',   'Full user management including password resets'),
        ('settings:read',         'settings',       'read',    'View system settings'),
        ('settings:write',        'settings',       'write',   'Modify system settings'),
        ('mail:read',             'mail',           'read',    'View mail gateway messages and logs'),
        ('mail:admin',            'mail',           'admin',   'Manage mail gateway configuration'),
        ('platform:admin',        'platform',       'admin',   'Platform-scoped configuration and Client Admin identity'),
        ('tenant:admin',          'tenant',         'admin',   'Tenant-scoped operational administration'),
        ('coa:import',            'coa',            'import',  'Bulk chart of accounts upload')
        ON CONFLICT (code) DO NOTHING;
    """))

    # ── 3. Role-permission mapping ────────────────────────────────────────────
    # Platform Admin (system@bp0.work) — Client Admin emails only (13 §5.9, 15 §8.11)
    op.execute(sa.text(f"""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT '{ROLE_PLATFORM_ADMIN}', id FROM permissions
        WHERE code IN (
            'platform:admin',
            'users:read', 'users:admin',
            'audit-logs:read'
        )
        ON CONFLICT DO NOTHING;
    """))

    # Client Admin (system.mmlogistix@bp0.work) — tenant operational config only
    op.execute(sa.text(f"""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT '{ROLE_CLIENT_ADMIN}', id FROM permissions
        WHERE code IN (
            'tenant:admin',
            'mail:read', 'mail:admin',
            'settings:read', 'settings:write',
            'coa:import'
        )
        ON CONFLICT DO NOTHING;
    """))

    # CFO: read all, approve tier 3, admin for approvals and journal entries
    op.execute(sa.text(f"""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT '{ROLE_CFO}', id FROM permissions
        WHERE code IN (
            'cases:read', 'cases:write',
            'approvals:read', 'approvals:approve', 'approvals:admin',
            'journal-entries:read', 'journal-entries:write',
            'policies:read', 'policies:write',
            'queues:read',
            'reconciliation:read', 'reconciliation:write',
            'audit-logs:read',
            'users:read',
            'settings:read', 'settings:write',
            'mail:read'
        )
        ON CONFLICT DO NOTHING;
    """))

    # Finance Manager: tier 2 approvals, manage team
    op.execute(sa.text(f"""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT '{ROLE_FINANCE_MANAGER}', id FROM permissions
        WHERE code IN (
            'cases:read', 'cases:write',
            'approvals:read', 'approvals:approve',
            'journal-entries:read', 'journal-entries:write',
            'policies:read',
            'queues:read',
            'reconciliation:read', 'reconciliation:write',
            'audit-logs:read',
            'users:read', 'users:write',
            'settings:read',
            'mail:read'
        )
        ON CONFLICT DO NOTHING;
    """))

    # Finance Officer: standard case work and tier 2 approvals
    op.execute(sa.text(f"""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT '{ROLE_FINANCE_OFFICER}', id FROM permissions
        WHERE code IN (
            'cases:read', 'cases:write',
            'approvals:read', 'approvals:approve',
            'journal-entries:read', 'journal-entries:write',
            'policies:read',
            'queues:read',
            'reconciliation:read', 'reconciliation:write',
            'mail:read'
        )
        ON CONFLICT DO NOTHING;
    """))

    # Accounts Clerk: data entry and case creation
    op.execute(sa.text(f"""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT '{ROLE_ACCOUNTS_CLERK}', id FROM permissions
        WHERE code IN (
            'cases:read', 'cases:write',
            'journal-entries:read',
            'reconciliation:read',
            'mail:read'
        )
        ON CONFLICT DO NOTHING;
    """))

    # Auditor: read-only everything
    op.execute(sa.text(f"""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT '{ROLE_AUDITOR}', id FROM permissions
        WHERE code IN (
            'cases:read',
            'approvals:read',
            'journal-entries:read',
            'policies:read',
            'reconciliation:read',
            'audit-logs:read',
            'users:read',
            'mail:read'
        )
        ON CONFLICT DO NOTHING;
    """))

    # General Manager: operational workflows, customer/vendor communications, escalations
    # The GM sits OUTSIDE the financial approval hierarchy (BRD §8).
    # GM has NO authority over accounting treatment, journal approval, or financial posting.
    # approvals:approve and journal-entries:write are intentionally absent.
    op.execute(sa.text(f"""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT '{ROLE_GENERAL_MANAGER}', id FROM permissions
        WHERE code IN (
            'cases:read',       -- view operational case status
            'cases:write',      -- add notes, handle operational exceptions
            'approvals:read',   -- monitor approval status for escalations
            'queues:read',      -- operational queue monitoring
            'mail:read'         -- customer/vendor communications
        )
        ON CONFLICT DO NOTHING;
    """))


def downgrade() -> None:
    # Remove role-permission mappings for seeded roles only
    op.execute(sa.text(f"""
        DELETE FROM role_permissions
        WHERE role_id IN (
            '{ROLE_PLATFORM_ADMIN}', '{ROLE_CLIENT_ADMIN}', '{ROLE_CFO}',
            '{ROLE_FINANCE_MANAGER}', '{ROLE_FINANCE_OFFICER}', '{ROLE_ACCOUNTS_CLERK}',
            '{ROLE_AUDITOR}', '{ROLE_GENERAL_MANAGER}'
        );
    """))

    # Remove seeded permissions
    op.execute(sa.text("""
        DELETE FROM permissions WHERE code IN (
            'cases:read', 'cases:write', 'cases:delete',
            'approvals:read', 'approvals:approve', 'approvals:admin',
            'journal-entries:read', 'journal-entries:write',
            'policies:read', 'policies:write',
            'queues:read', 'queues:admin',
            'reconciliation:read', 'reconciliation:write',
            'audit-logs:read',
            'users:read', 'users:write', 'users:admin',
            'settings:read', 'settings:write',
            'mail:read', 'mail:admin',
            'platform:admin', 'tenant:admin', 'coa:import'
        );
    """))

    # Remove seeded roles
    op.execute(sa.text(f"""
        DELETE FROM roles WHERE id IN (
            '{ROLE_PLATFORM_ADMIN}', '{ROLE_CLIENT_ADMIN}', '{ROLE_CFO}',
            '{ROLE_FINANCE_MANAGER}', '{ROLE_FINANCE_OFFICER}', '{ROLE_ACCOUNTS_CLERK}',
            '{ROLE_AUDITOR}', '{ROLE_GENERAL_MANAGER}'
        );
    """))
```

**File:** `migrations/versions/20260510_006c_seed_system_admin_users.py`

Runs immediately after `006b_create_password_history_table.py`. Seeds the two-tier system administrator accounts (`13` §5.9, `06` §19.8). DDL source: `06` §3.1.

```python
"""Seed platform and client system administrator users

Revision ID: 20260510_006c
Revises: 20260510_006b
"""

from alembic import op
import sqlalchemy as sa

revision = "20260510_006c"
down_revision = "20260510_006b"
branch_labels = None
depends_on = None

USER_PLATFORM_ADMIN = "00000000-0000-0000-0000-000000000100"
USER_CLIENT_ADMIN   = "00000000-0000-0000-0000-000000000101"
ROLE_PLATFORM_ADMIN = "00000000-0000-0000-0000-000000000001"
ROLE_CLIENT_ADMIN   = "00000000-0000-0000-0000-000000000008"


def upgrade() -> None:
    # password_hash must be replaced with a real Argon2id hash at deploy time
    op.execute(sa.text(f"""
        INSERT INTO users (id, username, display_name, email, password_hash, role_id, status, two_factor_enabled)
        VALUES
            ('{USER_PLATFORM_ADMIN}', 'system', 'BP0 Platform Administrator',
             'system@bp0.work', '[ARGON2ID_HASH_AT_MIGRATION]', '{ROLE_PLATFORM_ADMIN}', 'active', true),
            ('{USER_CLIENT_ADMIN}', 'system.mmlogistix', 'mmlogistix System Administrator',
             'system.mmlogistix@bp0.work', '[ARGON2ID_HASH_AT_MIGRATION]', '{ROLE_CLIENT_ADMIN}', 'active', true)
        ON CONFLICT (id) DO NOTHING;
    """))


def downgrade() -> None:
    op.execute(sa.text(f"""
        DELETE FROM users WHERE id IN ('{USER_PLATFORM_ADMIN}', '{USER_CLIENT_ADMIN}');
    """))
```

---

# 9. Shared Database Utilities

## 9.1 app/core/database.py

```python
# app/core/database.py
"""
Async SQLAlchemy engine and session factory.
Used by FastAPI dependency injection and background workers.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

engine = create_async_engine(
    settings.database_url,               # postgresql+asyncpg://...
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_pre_ping=True,                  # validates connections before use
    pool_recycle=settings.database_pool_recycle,
    echo=settings.database_echo,         # SQL logging (dev only)
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,              # objects remain usable after commit
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency: provides a database session per request.
    Rolls back on exception, always closes the session.

    Usage:
        @router.get("/cases")
        async def list_cases(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

## 9.2 Repository Base Class

```python
# app/repositories/base.py
"""
Generic repository base. Every table gets a repository class in
app/repositories/{domain}.py. No raw SQL outside repositories.
"""

from typing import Any, Generic, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    model: type[ModelT]

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, id: UUID) -> ModelT | None:
        result = await self.db.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()

    async def get_all(self, limit: int = 50, offset: int = 0) -> list[ModelT]:
        result = await self.db.execute(
            select(self.model).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    async def create(self, **kwargs: Any) -> ModelT:
        obj = self.model(**kwargs)
        self.db.add(obj)
        await self.db.flush()   # assigns DB-generated id without committing
        await self.db.refresh(obj)
        return obj

    async def delete(self, obj: ModelT) -> None:
        await self.db.delete(obj)
        await self.db.flush()
```

---

# 10. Migration Naming and Ordering Reference

This table is the single canonical mapping between the logical labels in `00_Project_Overview.md` §5.1 and the actual `.py` migration files. When `00` says `002_auth_rbac.sql`, the developer creates the six files in the Phase 2 block below.

| Phase | Logical Label (`00` §5.1) | Migration File (`.py`) | `06` §18.4 Name |
|-------|--------------------------|------------------------|-----------------|
| 2 | `002_auth_rbac.sql` | `20260510_143200_001_create_roles_table.py` | `001_create_roles_table` |
| 2 | `002_auth_rbac.sql` | `20260510_143300_002_create_permissions_table.py` | `002_create_permissions_table` |
| 2 | `002_auth_rbac.sql` | `20260510_143400_003_create_role_permissions_table.py` | `003_create_role_permissions_table` |
| 2 | `002_auth_rbac.sql` | `20260510_143500_004_create_users_table.py` | `004_create_users_table` |
| 2 | `002_auth_rbac.sql` | `20260510_143600_005_create_refresh_tokens_table.py` | `005_create_refresh_tokens_table` |
| 2 | `002_auth_rbac.sql` | `20260510_143700_006_seed_roles_and_permissions.py` | `006_seed_system_roles_and_permissions` |
| 2 | `002_auth_rbac.sql` | `006b_create_password_history_table.py` | `006b_create_password_history_table` — see note below |
| 3 | `003_mail_gateway.sql` | `007_create_emails_table.py` | `007_create_emails_table` |
| 3 | `003_mail_gateway.sql` | `008_create_email_attachments_table.py` | `008_create_email_attachments_table` |
| 3 | `003_mail_gateway.sql` | `009_create_mail_gateway_config_table.py` | `009_create_mail_gateway_config_table` |
| 4 | `004_workflow_policy.sql` | `010_create_counterparty_table.py` … `024_create_approval_configuration_table.py` | `010`–`024` per `06` §18.4 |
| 5 | `005_accounts_worker.sql` | `025_seed_default_policies.py`, `026_create_queue_messages_table.py` | `025`–`026` |
| 6–7 | `006_ar_worker.sql` / `007_ap_worker.sql` | `026b_create_purchase_orders_table.py` | `026b` — see note below |
| 6 | `006_ar_worker.sql` | `026c_add_ar_soa_request_case_type.py` | `026c` — ALTER TYPE only; see note below |
| 8 | `008_treasury.sql` | `027_create_coa_accounts_table.py` … `033_create_reconciliation_matches_table.py` | `027`–`033` |
| 9 | `009_approval_ui.sql` | `034_create_notification_templates_table.py` … `036_seed_notification_templates.py` | `034`–`036` |
| 10 | `010_monitoring_audit.sql` | `037_create_audit_logs_table.py` … `039_add_audit_log_partitioning.py` | `037`–`039` |
| 10 | `010_monitoring_audit.sql` | `039b_add_expense_claim_case_type.py` | `039b` — ALTER TYPE only; see note below |
| 11 | `011_expense_management.sql` | `040_create_expense_claims_table.py` … `044_seed_expense_policies.py` | `040`–`044` per `19` §11 |
| 11b | `011b_executive_email_sop.sql` | `045_create_finance_activity_log_and_mailbox_sop_columns.py` | `045` — see note below |
| 11b | `011b_executive_email_sop.sql` | `046_create_case_escalations_and_pending_outbound_emails.py` | `046` — see note below |
| 12 | Client Admin `047`–`053` | `047` … `053_accounting_period_types.py` | Shipped `0.14.4` — see `06` §18.4 |
| 12 | `054_remove_seed_coa_accounts.py` | `054` | Shipped `0.14.7` |
| 13 | `0.14.8-counterparty-accounts` | `055_create_counterparty_accounts_table.py` | `055` — see note below |
| 13 | `0.14.8-counterparty-accounts` | `056_create_payment_terms_table.py` | `056` — seed COD, NET7, NET30, NET60 |
| 13 | `0.14.8-counterparty-accounts` | `057_create_tenant_tax_codes_table.py` | `057` |
| 13 | `0.14.8-counterparty-accounts` | `058_cases_counterparty_account_fk.py` | `058` — `cases.counterparty_account_id` nullable FK |
| 14 | `0.14.9-binding-authority` | `059_seed_accounts_manager_user.py` | `059` — key-role user seed (if not already applied) |
| 14 | `0.14.9-binding-authority` | `060_binding_authority_thresholds.py` | `060` — seed/update `ap_approval_thresholds`, `ar_approval_thresholds`, `expense_approval_thresholds` JSON rules |
| 14 | `0.14.10-counterparty-fixes` | `061_counterparty_contract_fields.py` | `061` — add vendor contract columns + expiry warning settings to `counterparty` |

> **Binding authority (`0.14.9`, shipped):** **`060`** updates active `ap_approval_thresholds` and `ar_approval_thresholds` policies and inserts `expense_approval_thresholds` with default tier ceilings (3k / 10k / 10k), STP confidence 0.9, SLA 4h / 8h. No new tables — uses existing `policies.rules` JSONB (`06` §3.5). Implementation: `app/policies/binding_authority.py`, `app/services/binding_authority_service.py`, `PolicyEngine.evaluate_approval_tier`.

> **Vendor contract fields (`0.14.10`, shipped):** **`061`** adds optional vendor-contract metadata to `counterparty` (`has_contract`, `contract_reference`, `contract_start_date`, `contract_expiry_date`, `supplier_owner`, `contract_warning_days` default 30). Finance UI shows a warning badge when `contract_expiry_date` is within the per-vendor warning window; Client Admin dashboard adds a completeness warning for vendors expiring within 30 days.

> **Phase 13 counterparty subaccounts (`0.14.8`, planned):** Runs after **`054`** (or latest `053` head on branch). **`055`** creates `counterparty_accounts` (DDL `06` §4.1a). **`056`** creates `payment_terms` + seeds default terms. **`057`** creates `tenant_tax_codes`. **`058`** adds `cases.counterparty_account_id UUID REFERENCES counterparty_accounts(id)` and optional index. ORM (manual, follow §7 patterns): `app/models/counterparty.py` — `CounterpartyAccount`, `PaymentTerm`; `app/models/tax.py` or `tenant.py` — `TenantTaxCode`. Wire `Case.counterparty_account` relationship. API + workers per `03` §2.1, `17` §3.2.1–§3.2.3. Do **not** use autogenerate for seed data in `056`.

> **Phase 9 `notifications` table note:** The `notifications` inbox table (defined in `06` §3.9 and `18` §3) is created in **`035b_create_notifications_table.py`** — a dedicated migration immediately after `035_create_user_notification_preferences_table.py` and before `036_seed_notification_templates.py`. This gives each Phase 9 table its own migration file for clean scope and rollback granularity. The Phase 9 migration sequence is therefore: `034` → `035` → `035b` → `036`. See `06` §18.4 for the canonical Phase 9 migration list.

> **Phase 2 `password_history` table note:** The `password_history` table (defined in `06` §3.6) is created in **`006b_create_password_history_table.py`** — a dedicated migration inserted after `006_seed_roles_and_permissions.py`. It enforces the "cannot reuse last 5 passwords" security control in `13` §5.2. Like `035b` and `026b`, this file must be created manually with `down_revision` wired to `006`. Do **not** use `alembic revision --autogenerate` for this file. The table has no `updated_at` column and no `auto_update_timestamp` trigger. DDL source: `06` §3.6. ORM model: `app/models/user.py` `PasswordHistory` class (see §7.2).

> **Phase 2 system administrator users:** **`006c_seed_system_admin_users.py`** runs after `006b` and inserts `system@bp0.work` (`platform_admin`) and `system.mmlogistix@bp0.work` (`client_admin`) per `06` §19.8 and `13` §5.9. Complete worked example in §8 immediately following `006_seed_roles_and_permissions.py`.

> **Phase 6–7 `purchase_orders` table note:** The `purchase_orders` table (defined in `06` §13a) is created in **`026b_create_purchase_orders_table.py`** — a dedicated migration inserted between `026_create_queue_messages_table.py` (Phase 5) and `027_create_coa_accounts_table.py` (Phase 8). This is a prerequisite for AP Worker PO validation (`17` §5) and must be applied before Phase 7 AP Worker development begins. Like `035b`, this file must be created manually with `down_revision` wired to `026`. Do **not** use `alembic revision --autogenerate` for this file. See `06` §13a for the full DDL.

> **Phase 6 `ar_soa_request` enum value note:** The `ar_soa_request` case type (defined in `05` §5.3) must be added to the `case_type` PostgreSQL ENUM before Phase 6 AR Worker development begins. Create **`026c_add_ar_soa_request_case_type.py`** immediately after `026b` with `down_revision` wired to `026b`. Migration body: `op.execute("ALTER TYPE case_type ADD VALUE 'ar_soa_request';")`. No `downgrade()` is possible for `ADD VALUE` on PG < 14; on PG 14+ it is transactional. This is a `c`-suffix file — create manually, do not use `alembic revision --autogenerate`.

> **Phase 11 `expense_claim` enum value note:** The `expense_claim` case type (defined in `05` §5.3 and `19` §15 Note 2) is added to the `case_type` PostgreSQL ENUM in **`039b_add_expense_claim_case_type.py`** — a dedicated migration inserted between Phase 10's final migration (`039_add_audit_log_partitioning.py`) and Phase 11's first table migration (`040_create_expense_claims_table.py`). Migration body: `op.execute("ALTER TYPE case_type ADD VALUE 'expense_claim';")`. No `downgrade()` is possible for `ADD VALUE` on PG < 14; on PG 14+ it is transactional. Create this file manually with `down_revision` wired to the `039` revision ID. Do **not** use `alembic revision --autogenerate`. See `05` §5.3 for the canonical case types list.

> **Phase 11 note:** Migrations `040`–`044` are fully specified in `19_Expense_Worker_Specification.md` §11. This document (§8) provides complete migration files for Phase 2 only; Phase 11 follows the same patterns with DDL sourced from `19` §3.

> **Phase 11b `finance_activity_log` + SOP columns note:** Migration **`045_create_finance_activity_log_and_mailbox_sop_columns.py`** must run after `044` (after all Phase 11 expense migrations are complete). It performs three operations: (1) creates the `finance_activity_log` table (§7.4 of `06`) — append-only operational log powering the daily 9pm SGT digest to the CFO; (2) adds the `mailbox_mode`, `escalation_manager_email`, and `requires_outbound_client_approval` columns to `mail_gateway_config` (§7.3 of `06`); (3) backfills the new columns per the seed values in `06` §19.7. This migration is designated "Phase 11b" (Executive Email SOP — MVP; required for production). See `06` §18.4 Phase 11b block and `17` §10 for the full SOP specification. Create this file with `down_revision` wired to `044`.

> **Phase 11b escalation + outbound queue note:** Migration **`046_create_case_escalations_and_pending_outbound_emails.py`** runs after `045`. Creates `case_escalations`, `pending_outbound_emails`, and ENUMs per `06` §7.5–§7.6, including `pending_outbound_emails.rejection_reason_code` for manager reject when data was in body/attachment (`17` §10.5.5). Seed template `manager.outbound.approval.request` in `036` supplement or `045` seed block (`18` §7.7).

---

# 11. Common Patterns and Gotchas

## 11.1 ENUM Types

PostgreSQL native ENUM types must be created before the table that uses them, and dropped after the table in `downgrade()`. They are not managed by `op.create_table()`.

```python
# upgrade()
op.execute("CREATE TYPE case_status AS ENUM ('inbound', 'classified', 'processing', ...);")
op.execute("CREATE TYPE case_priority AS ENUM ('critical', 'high', 'medium', 'low');")
op.create_table("cases", ..., sa.Column("status", postgresql.ENUM(name="case_status"), ...))

# downgrade()
op.drop_table("cases")
op.execute("DROP TYPE IF EXISTS case_status;")
op.execute("DROP TYPE IF EXISTS case_priority;")
```

## 11.2 GIN Indexes

GIN indexes for full-text search and array operators must use `op.execute()`:

```python
# upgrade()
op.execute("""
    CREATE INDEX counterparty_name_tsvector_idx
    ON counterparty USING gin(to_tsvector('english', name));
""")
op.execute("CREATE INDEX cases_tags_idx ON cases USING gin(tags);")

# downgrade()
op.execute("DROP INDEX IF EXISTS counterparty_name_tsvector_idx;")
op.execute("DROP INDEX IF EXISTS cases_tags_idx;")
```

## 11.3 Self-Referential Foreign Key (cases.parent_case_id)

`cases.parent_case_id` references `cases.id` — the same table. Create the column nullable (no FK constraint initially), then add the FK constraint in the same migration after table creation:

```python
# In the cases table migration
op.create_table("cases", ..., sa.Column("parent_case_id", postgresql.UUID(as_uuid=True), nullable=True))
op.create_foreign_key(
    "cases_parent_case_id_fkey",
    "cases", "cases",
    ["parent_case_id"], ["id"],
)
```

## 11.4 Circular FK Between cases and emails

`cases.email_id` references `emails.id` and `emails.case_id` references `cases.id`. PostgreSQL can create both FK *constraints* once both tables exist, but Alembic cannot declare them inline in `CREATE TABLE` — whichever table is created second would try to reference a table that already exists but the reverse FK on the first table cannot be added during its own `CREATE TABLE` statement without the second table existing. The result is a migration that fails at `alembic upgrade head` on a clean database.

**Resolution:** create both columns as plain nullable `UUID` (no `REFERENCES` clause) in their respective `CREATE TABLE` migrations. Add **both** FK constraints at the end of `011_create_cases_table.py` — after both tables exist — using `op.create_foreign_key()`. The `downgrade()` must drop both constraints before dropping `cases`.

This is reflected in the DDL in `06_Database_Schema_Design.md`: `cases.email_id` and `emails.case_id` appear as bare `UUID` columns with a comment.

### Complete migration: 011_create_cases_table.py (FK section)

```python
"""create_cases_table

Revision ID: 20260510_011
Revises: 20260510_010
Create Date: 2026-05-10 14:41:00.000000

Creates the cases table. Also adds the two cross-FKs that form the circular
dependency between cases and emails:
  - cases.email_id  → emails.id
  - emails.case_id  → cases.id

Both columns were created as plain nullable UUID in their respective migrations
(007 for emails, 011 here for cases). The constraints are added here, at the
end of upgrade(), after both tables exist.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260510_011"
down_revision = "20260510_010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. ENUM types (created before the table) ────────────────────────────
    op.execute("""
        CREATE TYPE case_status AS ENUM (
            'inbound', 'classified', 'processing', 'pending_approval',
            'approved', 'posted', 'completed', 'rejected', 'exception',
            'manual_review', 'on_hold'
        );
    """)
    op.execute("""
        CREATE TYPE case_type AS ENUM (
            'ar_invoice', 'ar_payment_advice', 'ar_credit_note',
            'ap_invoice', 'ap_po_validation', 'ap_payment_proposal',
            'treasury_reconciliation', 'treasury_fx', 'treasury_suspense',
            'general_inquiry'
        );
    """)
    # ⚠️  ENUM EXTENSION NOTE: The values above are the Phase 4 baseline.
    # Two additional case types are required before later phases go live:
    #
    #   • 'ar_soa_request' — AR Worker (Phase 6). Add via a dedicated ALTER TYPE
    #     migration (e.g. 026c_add_ar_soa_request_case_type.py) before Phase 6.
    #   • 'expense_claim'  — Expense Worker (Phase 11). Add via the dedicated
    #     ALTER TYPE migration 039b_add_expense_claim_case_type.py, inserted
    #     between Phase 10's final migration (039) and Phase 11's first table
    #     migration (040_create_expense_claims_table.py).
    #
    # Both values are listed in the canonical case types table in
    # 05_API_Specification.md §5.3. ALTER TYPE syntax:
    #   op.execute("ALTER TYPE case_type ADD VALUE 'ar_soa_request';")
    #   op.execute("ALTER TYPE case_type ADD VALUE 'expense_claim';")
    # Note: PostgreSQL ALTER TYPE ADD VALUE cannot be rolled back inside a
    # transaction on PG < 14; test on PG 14+ where it is transactional.
    op.execute("CREATE TYPE case_priority AS ENUM ('critical', 'high', 'medium', 'low');")

    # ── 2. cases table — email_id is bare UUID (no REFERENCES yet) ──────────
    op.create_table(
        "cases",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            primary_key=True, server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("case_number", sa.String(20), nullable=False),
        sa.Column("type",     postgresql.ENUM(name="case_type",     create_type=False), nullable=False),
        sa.Column("status",   postgresql.ENUM(name="case_status",   create_type=False), nullable=False, server_default="inbound"),
        sa.Column("priority", postgresql.ENUM(name="case_priority", create_type=False), nullable=False, server_default="medium"),
        sa.Column("confidence_score", sa.Numeric(3, 2), nullable=True),
        sa.Column("stp_eligible", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("subject", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("counterparty_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("counterparty.id"), nullable=True),
        sa.Column("counterparty_name", sa.String(255), nullable=True),
        sa.Column("amount_value", sa.Numeric(19, 4), nullable=True),
        sa.Column("amount_currency", sa.CHAR(3), server_default="SGD"),
        sa.Column("converted_amount_value", sa.Numeric(19, 4), nullable=True),
        sa.Column("converted_amount_currency", sa.CHAR(3), server_default="SGD"),
        sa.Column("exchange_rate", sa.Numeric(19, 8), server_default="1.0"),
        sa.Column("assigned_to", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id"), nullable=True),
        sa.Column("current_approval_tier", sa.Integer, nullable=True),
        # email_id: bare UUID — FK constraint added below after emails table confirmed present
        sa.Column("email_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("parent_case_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("tags",       postgresql.ARRAY(sa.String(50)), server_default="{}"),
        sa.Column("risk_flags", postgresql.ARRAY(sa.String(50)), server_default="{}"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("classification_metadata", postgresql.JSONB, server_default="{}"),
        sa.Column("workflow_metadata",        postgresql.JSONB, server_default="{}"),
        sa.Column("sla_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sla_status", sa.String(20), nullable=True),
        sa.Column("created_by", sa.String(50), nullable=False, server_default="system"),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("due_date",      sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at",  sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("case_number", name="cases_case_number_key"),
        sa.CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 1",
            name="cases_confidence_score_check",
        ),
        sa.CheckConstraint(
            "current_approval_tier BETWEEN 1 AND 3",
            name="cases_approval_tier_check",
        ),
        sa.CheckConstraint(
            "sla_status IN ('on_track', 'at_risk', 'breached')",
            name="cases_sla_status_check",
        ),
    )

    # ── 3. Self-referential FK: cases.parent_case_id → cases.id ────────────
    op.create_foreign_key(
        "cases_parent_case_id_fkey", "cases", "cases",
        ["parent_case_id"], ["id"],
    )

    # ── 4. Indexes ───────────────────────────────────────────────────────────
    op.create_index("cases_case_number_idx",  "cases", ["case_number"])
    op.create_index("cases_type_idx",         "cases", ["type"])
    op.create_index("cases_status_idx",       "cases", ["status"])
    op.create_index("cases_priority_idx",     "cases", ["priority"])
    op.create_index("cases_email_id_idx",     "cases", ["email_id"])
    op.create_index("cases_counterparty_id_idx", "cases", ["counterparty_id"])
    op.execute("""
        CREATE INDEX cases_assigned_to_idx ON cases(assigned_to)
        WHERE assigned_to IS NOT NULL;
    """)
    op.execute("""
        CREATE INDEX cases_parent_case_id_idx ON cases(parent_case_id)
        WHERE parent_case_id IS NOT NULL;
    """)
    op.execute("""
        CREATE INDEX cases_sla_deadline_idx ON cases(sla_deadline)
        WHERE sla_status IN ('on_track', 'at_risk');
    """)
    op.execute("CREATE INDEX cases_tags_idx      ON cases USING gin(tags);")
    op.execute("CREATE INDEX cases_risk_flags_idx ON cases USING gin(risk_flags);")
    op.create_index("cases_status_priority_idx", "cases", ["status", "priority"])
    op.create_index("cases_type_status_idx",     "cases", ["type", "status"])
    op.create_index("cases_created_at_idx",      "cases", ["created_at"])

    # ── 5. updated_at trigger ────────────────────────────────────────────────
    op.execute("""
        CREATE TRIGGER cases_updated_at
            BEFORE UPDATE ON cases
            FOR EACH ROW EXECUTE FUNCTION auto_update_timestamp();
    """)

    # ── 6. Cross-FKs (circular dependency resolution) ───────────────────────
    # Both tables now exist. Add the two FKs that form the cases ↔ emails
    # circular dependency. Neither could be declared inline in CREATE TABLE.
    op.create_foreign_key(
        "cases_email_id_fkey",           # constraint name
        "cases", "emails",               # source table, referencing table
        ["email_id"], ["id"],            # source columns, referenced columns
    )
    op.create_foreign_key(
        "emails_case_id_fkey",
        "emails", "cases",
        ["case_id"], ["id"],
    )


def downgrade() -> None:
    # Drop the cross-FKs FIRST — before either table is dropped
    op.drop_constraint("emails_case_id_fkey",  "emails", type_="foreignkey")
    op.drop_constraint("cases_email_id_fkey",  "cases",  type_="foreignkey")

    # Drop the self-referential FK
    op.drop_constraint("cases_parent_case_id_fkey", "cases", type_="foreignkey")

    # Drop triggers and indexes
    op.execute("DROP TRIGGER IF EXISTS cases_updated_at ON cases;")
    op.execute("DROP INDEX IF EXISTS cases_sla_deadline_idx;")
    op.execute("DROP INDEX IF EXISTS cases_parent_case_id_idx;")
    op.execute("DROP INDEX IF EXISTS cases_assigned_to_idx;")
    op.execute("DROP INDEX IF EXISTS cases_tags_idx;")
    op.execute("DROP INDEX IF EXISTS cases_risk_flags_idx;")
    op.drop_index("cases_type_status_idx",     table_name="cases")
    op.drop_index("cases_status_priority_idx", table_name="cases")
    op.drop_index("cases_created_at_idx",      table_name="cases")
    op.drop_index("cases_email_id_idx",        table_name="cases")
    op.drop_index("cases_counterparty_id_idx", table_name="cases")
    op.drop_index("cases_priority_idx",        table_name="cases")
    op.drop_index("cases_status_idx",          table_name="cases")
    op.drop_index("cases_type_idx",            table_name="cases")
    op.drop_index("cases_case_number_idx",     table_name="cases")

    op.drop_table("cases")

    op.execute("DROP TYPE IF EXISTS case_priority;")
    op.execute("DROP TYPE IF EXISTS case_type;")
    op.execute("DROP TYPE IF EXISTS case_status;")
```

### ORM model implications

The SQLAlchemy ORM models for `Case` and `Email` must reflect the deferred constraint. Use `foreign_keys` explicitly to avoid ambiguity:

```python
# app/models/case.py (relevant excerpt)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import ForeignKey
import uuid

class Case(Base, TimestampMixin):
    __tablename__ = "cases"

    # email_id has no inline ForeignKey() in create_table, but the DB constraint
    # exists after migration 011. Declare it here so ORM relationship works.
    email_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("emails.id"),        # matches the constraint added in migration 011
        nullable=True,
    )
    email: Mapped["Email | None"] = relationship(
        "Email",
        back_populates="case",
        foreign_keys="[Case.email_id]",  # explicit — avoids ambiguity with Email.case_id
    )

# app/models/email.py (relevant excerpt)
class Email(Base):
    __tablename__ = "emails"

    case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cases.id"),         # matches the constraint added in migration 011
        nullable=True,
    )
    case: Mapped["Case | None"] = relationship(
        "Case",
        back_populates="email",
        foreign_keys="[Email.case_id]",
    )
```

### Accounts Worker write order

The Accounts Worker (Phase 5) must set both FKs within a single transaction after both rows exist. The correct sequence:

```python
async with db.begin():
    # 1. Insert case with email_id=None (emails row already exists)
    new_case = Case(email_id=None, ...)
    db.add(new_case)
    await db.flush()          # assigns new_case.id without committing

    # 2. Set email.case_id now that the case row exists
    await db.execute(
        update(Email)
        .where(Email.id == email_id)
        .values(case_id=new_case.id, case_number=new_case.case_number)
    )

    # 3. Set case.email_id now that the email row is confirmed updated
    new_case.email_id = email_id

    # Transaction commits here — both FKs satisfied, both rows exist
```

Both `cases.email_id` and `emails.case_id` are nullable, so neither constraint fires until the value is set. The single transaction guarantees atomicity: if any step fails, neither row is partially updated.

## 11.5 Row Level Security (RLS)

RLS policies must be enabled and created via `op.execute()`. They cannot be expressed in `op.create_table()`.

```python
# upgrade() — after create_table
op.execute("ALTER TABLE cases ENABLE ROW LEVEL SECURITY;")
op.execute("""
    CREATE POLICY cases_select ON cases
        FOR SELECT USING (
            assigned_to = app_user_id()
            OR EXISTS (
                SELECT 1 FROM role_permissions rp
                JOIN users u ON u.role_id = rp.role_id
                JOIN permissions p ON p.id = rp.permission_id
                WHERE u.id = app_user_id() AND p.code = 'cases:read'
            )
        );
""")
-- Note: app_user_id() is a PostgreSQL session variable wrapper set by FastAPI middleware.
-- auth.uid() (Supabase PostgREST) is NOT available in this FastAPI + asyncpg architecture.
-- See 06_Database_Schema_Design.md §16.0 and 13_Security_and_Compliance_Specification.md §5.8.

# downgrade()
op.execute("DROP POLICY IF EXISTS cases_select ON cases;")
op.execute("ALTER TABLE cases DISABLE ROW LEVEL SECURITY;")
```

## 11.6 Testing Migrations in CI

Add this to the CI pipeline (GitHub Actions) to validate migrations on every PR:

```yaml
# .github/workflows/ci.yml (excerpt)
- name: Run migrations
  env:
    FINANCE_DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/finance_test
  run: |
    alembic upgrade head
    alembic check           # fails if there are unapplied migrations not in versions/

- name: Test downgrade
  run: |
    alembic downgrade base  # full rollback to empty schema
    alembic upgrade head    # re-apply — must succeed cleanly
```

## 11.7 Adding a Column to an Existing Table

Never edit a committed migration. Create a new one:

```python
# New migration file
def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("general_manager_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "users_general_manager_id_fkey",
        "users", "users",
        ["general_manager_id"], ["id"],
    )

def downgrade() -> None:
    op.drop_constraint("users_general_manager_id_fkey", "users", type_="foreignkey")
    op.drop_column("users", "general_manager_id")
```

---

# Version History

| Version | Date | Changes |
|---------|------|---------|
| 2.7 | 2026-05-26 | **`0.14.9-binding-authority`.** Migration `060` approval threshold policies; `059` accounts manager seed. |
| 2.6 | 2026-05-20 | **Phase 13 shipped (`0.14.8`).** Migrations `055`–`058` in production; git `b1095c1`–`b749e64`. |
| 2.5 | 2026-05-20 | **Phase 13 (`0.14.8`, planned).** §10: migrations `055`–`058`; ORM/service implementation map in footnote. Cross-ref `03` §2.1, `06` §4.1a–c. |
| 2.4 | 2026-05-19 | **Email SOP migrations.** §10: migration `046_create_case_escalations_and_pending_outbound_emails.py` row and footnote (`case_escalations`, `pending_outbound_emails`, `rejection_reason_code` per `06` §7.5–§7.6). Runs after `045`. Cross-ref `17` §10, `05` §8.8a–§8.8b. |
| 2.3 | 2026-05-19 | **Audit corrections (doc-suite audit).** OBS 3: Added Phase 11b row (`045_create_finance_activity_log_and_mailbox_sop_columns.py`) to §10 Migration Naming and Ordering Reference table. Added footnote documenting `045` scope (creates `finance_activity_log`, adds SOP columns to `mail_gateway_config`, backfills seed data), `down_revision` wiring to `044`, and cross-references to `06` §7.3–§7.4 and `17` §10. Consistent with `06` §18.4 Phase 11b block (v2.9.6). Added `20_Git_Workflow_and_Prompt_Management.md` and `21_openapi.yaml` rows to Companion Documents table. |
| 2.2 | 2026-05-19 | **Two-tier administration migrations.** Updated `006_seed_roles_and_permissions.py`: `ROLE_PLATFORM_ADMIN`, `ROLE_CLIENT_ADMIN`; permissions `platform:admin`, `tenant:admin`, `coa:import` (25 total); `platform_admin` limited to `platform:admin` + `users:admin`; `client_admin` gets `tenant:admin`, `mail:admin`, `coa:import`; CFO no longer receives `mail:admin`. Added worked example `006c_seed_system_admin_users.py` and Phase 2 footnotes for `006d` (`tenants`). Aligned with `06` §19.3, `13` §5.9, `15` §8.11–8.16. |
| 1.9 | 2026-05-19 | Supabase Cloud adoption: added §2.3 (Supabase Cloud — Connection and CLI) with project ref `ehsoeyfopazodvmpkkpy`, direct and async connection string formats, PostgreSQL 17.6.1.121 / PostgREST 14.5 / GoTrue 2.189.0 version details, CLI link commands, and anon key guidance (not required — server-side only). Updated §2.1 stack table to include Supabase Cloud as the managed database. Updated §4.2 `env.py` `get_url()` docstring to show the actual cloud host. Alembic-only migration management (never via Supabase dashboard) made explicit. |
| 1.8 | 2026-05-18 | Fix (GAP-4 from audit): Added `PasswordHistory` ORM model to §7.2 `app/models/user.py` — class with `id`, `user_id` (FK CASCADE), `password_hash`, `created_at`; no `updated_at` (append-only). Added `password_history` relationship to `User` model. Added `006b_create_password_history_table` row to §10 migration reference table (Phase 2, after `006`). Added `006b` footnote to §10 notes block with manual-creation instructions, `down_revision` wiring, and DDL source reference. Updated §10 Phase 9 `notifications` note to reference `§3.9` (renumbered from §3.8 in `06` v2.3.0). Schema DDL source: `06_Database_Schema_Design.md` §3.6 (added in same pass). |
| 1.7 | 2026-05-17 | Fix (M-4 from audit): Corrected `Permission.created_at` type annotation in §7.1 from `Mapped[uuid.UUID]` to `Mapped[datetime]` — using `uuid.UUID` as the type hint on a `DateTime(timezone=True)` column was a direct type-system bug that would cause runtime errors. Added `from datetime import datetime` import inline with the column. Applied same fix to `RolePermission.created_at` which had the identical bug. Fix (M-1 from audit): Made `expense_claim` ENUM extension migration placement definitive — replaced ambiguous "either `039b` or `040`" footnote with a firm decision: **`039b_add_expense_claim_case_type.py`** is a dedicated migration between Phase 10 (`039`) and Phase 11 (`040`). Added `039b` as an explicit row to §10 migration reference table. Fix (document suite review): Corrected version history row ordering — rows v1.3 and v1.6 had been inserted out of ascending sequence; all rows now appear in correct ascending order (v1.0 → v1.7). Same class of ordering bug previously fixed in `06` v1.7.0, `01` v4.4, and `01` v4.8. |
| 1.6 | 2026-05-16 | Fix (Issue 2 from audit): Added `⚠️ ENUM EXTENSION NOTE` to §11.4 migration `011` example — documents that `ar_soa_request` (Phase 6) and `expense_claim` (Phase 11) must be added to the `case_type` ENUM via subsequent `ALTER TYPE` migrations, with ALTER TYPE syntax and a PostgreSQL transaction note. Added `026c_add_ar_soa_request_case_type.py` row to §10 migration reference table (Phase 6, `c`-suffix, manual creation). Added two new footnotes to §10: one for `026c` (`ar_soa_request`) and one for the `expense_claim` enum extension (either in `040` or a dedicated `039b`). Both values are defined in `05_API_Specification.md` §5.3. |
| 1.5 | 2026-05-15 | Fix (GAP-3 from audit): Added `026b_create_purchase_orders_table.py` row to §10 Migration Naming and Ordering Reference table under Phase 6–7. Added corresponding footnote documenting the `b`-suffix exception, manual creation requirement, `down_revision` wiring to `026`, and DDL source reference (`06` §13a). This migration is the prerequisite for AP Worker PO validation (`17` §5) and must be applied before Phase 7 development begins. |
| 1.4 | 2026-05-15 | Fix (INC-3 from audit): Added `035b` naming exception note to §2.2 (Migration File Naming) and §6 (Authoring Rules). The `b` suffix is non-standard and requires manual file creation — `alembic revision --autogenerate` will not produce it. Manual `down_revision` wiring instructions added to §2.2. Fix (MIN-5 from audit): Corrected §11.5 RLS example to use `app_user_id()` instead of `auth.uid()` — `auth.uid()` is unavailable in this FastAPI + asyncpg architecture (documented in `06_Database_Schema_Design.md` §16.0 and `13_Security_and_Compliance_Specification.md` §5.8). |
| 1.3 | 2026-05-15 | Fix (Audit GAP 1): Resolved Phase 9 `notifications` migration ambiguity in §10 footnote — replaced "at developer's discretion (035b or 036)" with a firm decision: `035b_create_notifications_table.py` is a dedicated migration between `035` and `036`, giving each Phase 9 table its own file. Migration sequence is now explicit: `034` → `035` → `035b` → `036`. Consistent with `06_Database_Schema_Design.md` §3.8 and §18.4 (also updated in this audit pass). |
| 1.2 | 2026-05-15 | Fix (Issue 10 from audit): Added Phase 11 row (`040`–`044`, sourced from `19` §11) to §10 Migration Naming and Ordering Reference table. Added two footnotes below the table: (1) Phase 9 `notifications` table note clarifying that migration `035b` or `036` covers the third notification table (`notifications` inbox per `06` §3.8 / `18` §3); (2) Phase 11 note pointing developers to `19` §11 for the complete migration files. |
| 1.1 | 2026-05-15 | Fix (Issue 2.5): Added §1.4 Document Scope — explicit statement that complete migration files are provided for Phase 2 only, plus a Phase-specific DDL source reference table mapping every phase (2–11) to its authoritative DDL document and section. Restores the section separator and `# 2.` heading inadvertently removed in restructuring. |
| 1.0 | 2026-05-11 | Initial release — Alembic/SQLAlchemy conflict resolution (§1), `alembic.ini` / `env.py` config (§4), migration authoring rules (§6), SQLAlchemy base & mixins (§5), complete Phase 2 migration files (§8), shared DB utilities (§9), migration naming reference (§10), common patterns and gotchas (§11) |
