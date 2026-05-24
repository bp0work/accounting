"""Backward-compatible re-export — use `mail_actions` module."""

from app.api.routes.mail_actions import router

__all__ = ["router"]
