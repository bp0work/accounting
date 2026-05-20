FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY app ./app
COPY workers ./workers
COPY agents ./agents

RUN pip install --no-cache-dir -e ".[dev]"

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

EXPOSE 8013

CMD ["uvicorn", "workers.treasury.main:app", "--host", "0.0.0.0", "--port", "8013"]
