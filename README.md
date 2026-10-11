# Workcove backend

Local development runs with Docker Compose. The web, Celery, and Celery beat images are built as your macOS user so files written in the container stay owned by you.

## Start

```bash
APP_USER=$(id -un) APP_UID=$(id -u) docker compose -f docker-compose_dev.yml up -d --build
```

The API is at http://localhost:8000/.

## Stop

```bash
docker compose -f docker-compose_dev.yml down
```

`APP_USER` and `APP_UID` are only needed for the build. Stopping the containers does not remove the Postgres data directory on the host.
