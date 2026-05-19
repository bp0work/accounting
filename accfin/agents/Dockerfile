FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY agents ./agents

RUN pip install --no-cache-dir fastapi uvicorn httpx pydantic-settings

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV HERMES_PORT=8001

EXPOSE 8001

CMD ["uvicorn", "agents.hermes.main:app", "--host", "0.0.0.0", "--port", "8001"]
