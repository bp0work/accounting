#!/usr/bin/env python3
"""Generate secrets for .env — per `03` §6 Phase 1 and `14` §19."""

import secrets

print("# Generated secrets — merge into accfin/.env (do not commit .env)")
print(f"FINANCE_REDIS__PASSWORD={secrets.token_urlsafe(32)}")
print(f"FINANCE_HERMES_API_KEY={secrets.token_hex(32)}")
print(f"FINANCE_JWT__SECRET_KEY={secrets.token_urlsafe(48)}")
print(f"FINANCE_JWT__REFRESH_SECRET_KEY={secrets.token_urlsafe(48)}")
print(f"FINANCE_PRIVACY_ENCRYPTION_KEY={secrets.token_urlsafe(32)}")
print(f"FINANCE_INTERNAL_CRON_TOKEN={secrets.token_urlsafe(32)}")
