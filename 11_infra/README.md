# 11_infra

Local development infrastructure: docker compose stack, dev runner, and the
postgres bootstrap init script.

## Layout

```text
11_infra/
├── docker-compose.yml   # postgres, valkey, minio, nats, backend, frontend
├── dev.sh               # local fast-iteration runner (host processes)
├── postgres/
│   └── init.sql         # creates tennetctl_read / tennetctl_write roles
└── README.md
```

## Quick start

```bash
# from anywhere in the repo
11_infra/dev.sh start
```

This:

1. Starts docker compose infra (postgres on **55432**, valkey on 6379, minio
   on 9000/9001, nats on 4222/8222).
2. Starts the FastAPI backend as a host process via `uvicorn --reload` on
   **127.0.0.1:58000**.
3. Starts the Next.js frontend as a host process via `next dev` on
   **127.0.0.1:53000**.
4. Wipes `08_logs/` and tees both processes' stdout/stderr into
   `08_logs/backend.log` and `08_logs/frontend.log`.

## Commands

| Command                          | Effect                                              |
| -------------------------------- | --------------------------------------------------- |
| `11_infra/dev.sh start`          | Reset logs, ensure infra up, start backend+frontend |
| `11_infra/dev.sh stop`           | Stop backend + frontend (infra keeps running)       |
| `11_infra/dev.sh restart`        | `stop` then `start`                                 |
| `11_infra/dev.sh down`           | Stop everything including docker infra             |
| `11_infra/dev.sh status`         | Show what's currently running                       |
| `11_infra/dev.sh logs`           | Tail both log files                                 |
| `11_infra/dev.sh logs backend`   | Tail just `08_logs/backend.log`                     |
| `11_infra/dev.sh logs frontend`  | Tail just `08_logs/frontend.log`                    |

## Production build (full container)

For an end-to-end image build (no host processes):

```bash
cd 11_infra
docker compose build           # build backend + frontend images
docker compose up -d            # everything in containers
```

The container build is the source of truth for production. `dev.sh` exists
only to skip the rebuild loop during local iteration.

## Ports

| Service   | Host port | Container port | Notes                                    |
| --------- | --------- | -------------- | ---------------------------------------- |
| postgres  | 55432     | 5432           | Deliberately high to avoid host clashes  |
| backend   | 58000     | 8000           | FastAPI                                  |
| frontend  | 53000     | 3000           | Next.js                                  |
| valkey    | 6379      | 6379           | Standard                                 |
| minio S3  | 9000      | 9000           | Standard                                 |
| minio UI  | 9001      | 9001           | Console                                  |
| nats      | 4222      | 4222           | Client                                   |
| nats mon  | 8222      | 8222           | HTTP monitoring                          |

## Security posture (containers)

The `backend` and `frontend` services run with:

- **Non-root user** (uid 10001 backend, uid 10002 frontend)
- **Read-only root filesystem** with a 64M `tmpfs` for `/tmp`
- **All Linux capabilities dropped** (`cap_drop: ALL`)
- **`no-new-privileges`** so setuid binaries cannot escalate

`dev.sh` runs them as host processes for the inner-loop dev experience and
does not enforce these constraints — they apply only to the
`docker compose up backend frontend` path.
