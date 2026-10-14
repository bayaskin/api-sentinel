
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN python -m pip install --no-cache-dir . \
    && useradd --create-home --uid 10001 sentinel \
    && mkdir -p /work \
    && chown sentinel:sentinel /work

ENV HOME=/home/sentinel

USER sentinel

WORKDIR /work

ENTRYPOINT ["api-sentinel"]
