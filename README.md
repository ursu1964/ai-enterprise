# AI Enterprise

This repository converts an AI-Enterprise Manifest into a complete software system.

Controlled, auditable software-engineering orchestration platform. Python sources remain under
`apps/api/src`; the repository intentionally does not duplicate a root `src` tree.

## Development

```bash
cp .env.example .env
docker compose up --build -d
make check
```

Endpoints: `/`, `/health/live`, `/health/ready`, `/docs`, and `/metrics`.
PostgreSQL and the API bind to localhost. Compose runs migrations before the API, and the API image
runs as UID/GID 10001 with a read-only root filesystem and writable `/tmp`.

See [local bootstrap](docs/local-bootstrap.md) for development identities and providers.
