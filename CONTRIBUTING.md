# Contributing

```bash
pip install -e ".[dev]"
pytest tests/ -v
agentbox serve
curl http://localhost:8080/health
```

Docker:

```bash
docker compose up agentbox
docker compose run --rm test
```
