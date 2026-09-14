# Contributing

## Running tests

Prefer Docker Compose:

```bash
docker compose run --rm test
docker compose up agentbox   # API on :8080 for manual checks
```

Locally:

```bash
pip install -e ".[dev]"
pytest tests/ -v
agentbox serve
curl http://localhost:8080/health
```

## Pull requests

- Treat sandbox changes as security-sensitive; document limitations honestly
- Update README/CHANGELOG for API or limit changes
- Prefer small PRs with a clear test plan

## Commit style

- Imperative subject line; mention the user-facing why when relevant
- Do not add AI co-author trailers (e.g. Co-authored-by: Cursor) to commits.
