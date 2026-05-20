"""system_settings key-value store — `06` §13.2."""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import SystemSetting


class SystemSettingsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_value(self, key: str, default: str | None = None) -> str | None:
        result = await self._session.execute(
            select(SystemSetting.value).where(SystemSetting.key == key)
        )
        row = result.scalar_one_or_none()
        return row if row is not None else default

    async def get_int(self, key: str, default: int) -> int:
        raw = await self.get_value(key)
        if raw is None:
            return default
        try:
            return int(raw)
        except ValueError:
            return default

    async def set_value(self, key: str, value: str) -> None:
        stmt = (
            insert(SystemSetting)
            .values(key=key, value=value, value_type="string", category="mail")
            .on_conflict_do_update(
                index_elements=["key"],
                set_={"value": value},
            )
        )
        await self._session.execute(stmt)
        await self._session.commit()
