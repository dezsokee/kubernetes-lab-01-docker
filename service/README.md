# snipbox — Lab 1 service

A small HTTP API written in **Python 3.14 / FastAPI** that stores short text
snippets in **SQLite**. Unlike the in-memory reference examples, this one keeps
its data in a file under `/data`, so it needs a **volume** to survive a
container restart.

- Container port: **8080** (published on host **8400** by `docker-compose.yml`)
- Swagger UI: <http://localhost:8400/docs>
- Database file: `/data/snipbox.db` (override with `SNIPBOX_DB_PATH`)

## API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Service metadata |
| `GET` | `/health` | Liveness probe, also reports the snippet count |
| `POST` | `/snippets` | Create a snippet, returns `201` and an 8-char id |
| `GET` | `/snippets?limit=&offset=` | List snippets, newest first |
| `GET` | `/snippets/{id}` | Read one snippet, `404` if unknown |
| `DELETE` | `/snippets/{id}` | Delete one snippet, `204` / `404` |

`POST /snippets` takes `content` (required, 1..64000 chars), plus optional
`title` (default `untitled`) and `language` (default `text`). Validation errors
come back as `422`.

## Run it

```bash
docker compose up --build -d
curl -s localhost:8400/health
```

```bash
# create
curl -s -X POST localhost:8400/snippets \
  -H 'Content-Type: application/json' \
  -d '{"title":"hello","language":"python","content":"print(\"hi\")"}'
# {"id":"Yd8kQ1Zt","title":"hello","language":"python","content":"print(\"hi\")","created_at":"..."}

# read it back
curl -s localhost:8400/snippets/Yd8kQ1Zt
```

Persistence check — the data outlives the container, because it lives in the
named volume `snipbox-data`:

```bash
docker compose down        # container gone, volume kept
docker compose up -d
curl -s localhost:8400/snippets   # the snippet is still listed
docker compose down -v     # this also drops the volume, data is gone
```

## Publish

The image is published to the GitHub Container Registry:

```bash
docker build -t snipbox:1.0.0 service/   # from the repository root
docker login ghcr.io -u dezsokee         # password = PAT with write:packages
docker tag snipbox:1.0.0 ghcr.io/dezsokee/snipbox:1.0.0
docker tag snipbox:1.0.0 ghcr.io/dezsokee/snipbox:latest
docker push ghcr.io/dezsokee/snipbox:1.0.0
docker push ghcr.io/dezsokee/snipbox:latest
```

A freshly pushed package is **private** by default. Make it public under
*GitHub -> Packages -> snipbox -> Package settings -> Change visibility*,
otherwise `docker pull` needs credentials.

## Develop locally

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
pytest
SNIPBOX_DB_PATH=./data/snipbox.db uvicorn app.main:app --reload --port 8400
```