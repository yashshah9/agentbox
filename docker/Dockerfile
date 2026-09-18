FROM python:3.12-slim AS base
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends nodejs && rm -rf /var/lib/apt/lists/*

FROM base AS dev
COPY pyproject.toml README.md ./
COPY src ./src
COPY tests ./tests
RUN pip install --no-cache-dir -e ".[dev]"
CMD ["pytest", "tests/", "-v"]

FROM base AS runtime
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .
EXPOSE 8080
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health')"
CMD ["agentbox", "serve", "--host", "0.0.0.0", "--port", "8080"]

# Docker sandbox backend: needs docker CLI + mounted docker.sock (see compose profile).
# Nested `docker run -v` requires TMPDIR bind-mounted at the same absolute host path.
FROM runtime AS runtime-docker
RUN apt-get update && apt-get install -y --no-install-recommends docker-cli \
  && rm -rf /var/lib/apt/lists/*
ENV AGENTBOX_SANDBOX_BACKEND=docker
