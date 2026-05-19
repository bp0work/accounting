import os

os.environ.setdefault("FINANCE_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres")
os.environ.setdefault("FINANCE_REDIS__PASSWORD", "test-redis-password")
