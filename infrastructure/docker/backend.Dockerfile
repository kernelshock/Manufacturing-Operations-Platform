FROM python:3.14-slim@sha256:cd89c30eda26ee911a4611b18680086e0ea42e6f5f8cbe653d07fa7958c9cec8

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN groupadd --system mop && useradd --system --gid mop --home-dir /app mop

COPY pyproject.toml README.md requirements-prod.lock.txt ./
COPY src ./src
COPY migrations ./migrations
COPY alembic.ini ./

RUN python -m pip install --no-cache-dir -c requirements-prod.lock.txt .

RUN chown -R mop:mop /app
USER mop

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "mop.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
