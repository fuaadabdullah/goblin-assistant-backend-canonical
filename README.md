```markdown
# GoblinOS Assistant — Backend

This is the backend service for GoblinOS Assistant. It's a FastAPI application responsible for:

- Routing chat and debug requests to local or cloud LLM providers
- Managing user authentication (JWT, Google OAuth, WebAuthn passkeys)
- Task execution orchestration via GoblinOS integration
- Monitoring, structured logs, Prometheus metrics
- Background health probes for providers and RQ/Redis workers for background tasks

Core languages & frameworks:
- Python 3.11
- FastAPI
- SQLAlchemy (SQLite/Postgres)
- Redis + RQ for background tasks
- Prometheus and structured logging

## Quick Start (Local Dev)

1. Create Python venv:
```bash
cd apps/goblin-assistant/backend
python3 -m venv ../venv
source ../venv/bin/activate
pip install -r requirements.txt
```

2. Configure environment variables (copy `.env.example` to `.env`):
```bash
cp .env.example .env
# Update env values: DATABASE_URL, ROUTING_ENCRYPTION_KEY, JWT_SECRET_KEY, LOCAL_LLM_API_KEY
```

3. Start the backend:
```bash
uvicorn main:app --reload --port 8001
```

4. Verify the health endpoint:
```bash
curl http://localhost:8001/health
```

## Key Endpoints

- `GET /` - Root
- `GET /health` - Health
- `POST /chat/completions` - Chat completions (intelligent routing)
- `POST /debugger/suggest` - Debugger endpoint
- `POST /parse` - Natural-language orchestration parser
- `POST /execute` - Execute Goblin tasks
- `GET /metrics` - Prometheus metrics

## Environment Variables (Essential)

- `DATABASE_URL` - e.g., `sqlite:///./goblin_assistant.db` or Postgres
- `JWT_SECRET_KEY` - JWT signing key for auth
- `ROUTING_ENCRYPTION_KEY` - Base64 Fernet key to encrypt provider API keys
- `REDIS_URL` - Redis connection string for RQ and challenge store
- `LOCAL_LLM_PROXY_URL` - Local LLM proxy base URL
- `LOCAL_LLM_API_KEY` - X-API-Key for the local LLM proxy

## Production Checklist & Security

- Use a secrets manager for keys or encrypt them in DB using `ROUTING_ENCRYPTION_KEY`.
- Switch to Redis-backed rate limiting; replace in-memory rate limiter in `backend/middleware/rate_limiter.py`.
- Use `USE_REDIS_CHALLENGES=true` for passkey challenge store in production.
- Ensure TLS termination and enforce strong CORS policies.
- Confirm RQ workers (background tasks) are connected to a secure Redis instance.
- Enable Prometheus scraping and configure alerting for provider errors, high latency, and high error rate.

## Tests
```bash
cd apps/goblin-assistant/backend
pytest -v
```

## Docker

- `apps/goblin-assistant/Dockerfile` builds the backend image.
- The container runs `python start_server.py` and listens on port 8001 by default.

## Notes & Maintenance

- Keep the `providers/` adapters updated for new LLM providers.
- Periodically run `ProviderProbeWorker` to collect provider metrics and rotate provider keys accordingly.

## Canonical Documentation

All backend-focused documentation (endpoint audits, monitoring, production quickstarts, fixes, and integration notes) has been centralized under: `apps/goblin-assistant/backend/docs`.

Please update or add backend documentation in that folder so the canonical backend repository contains all backend-specific docs.

**Last Updated**: Dec 3, 2025
```
# Supabase CLI

[![Coverage Status](https://coveralls.io/repos/github/supabase/cli/badge.svg?branch=main)](https://coveralls.io/github/supabase/cli?branch=main) [![Bitbucket Pipelines](https://img.shields.io/bitbucket/pipelines/supabase-cli/setup-cli/master?style=flat-square&label=Bitbucket%20Canary)](https://bitbucket.org/supabase-cli/setup-cli/pipelines) [![Gitlab Pipeline Status](https://img.shields.io/gitlab/pipeline-status/sweatybridge%2Fsetup-cli?label=Gitlab%20Canary)
](https://gitlab.com/sweatybridge/setup-cli/-/pipelines)

[Supabase](https://supabase.io) is an open source Firebase alternative. We're building the features of Firebase using enterprise-grade open source tools.

This repository contains all the functionality for Supabase CLI.

- [x] Running Supabase locally
- [x] Managing database migrations
- [x] Creating and deploying Supabase Functions
- [x] Generating types directly from your database schema
- [x] Making authenticated HTTP requests to [Management API](https://supabase.com/docs/reference/api/introduction)

## Getting started

### Install the CLI

Available via [NPM](https://www.npmjs.com) as dev dependency. To install:

```bash
npm i supabase --save-dev
```

To install the beta release channel:

```bash
npm i supabase@beta --save-dev
```

When installing with yarn 4, you need to disable experimental fetch with the following nodejs config.

```
NODE_OPTIONS=--no-experimental-fetch yarn add supabase
```

> **Note**
For Bun versions below v1.0.17, you must add `supabase` as a [trusted dependency](https://bun.sh/guides/install/trusted) before running `bun add -D supabase`.

<details>
  <summary><b>macOS</b></summary>

  Available via [Homebrew](https://brew.sh). To install:

  ```sh
  brew install supabase/tap/supabase
  ```

  To install the beta release channel:

  ```sh
  brew install supabase/tap/supabase-beta
  brew link --overwrite supabase-beta
  ```

  To upgrade:

  ```sh
  brew upgrade supabase
  ```
</details>

<details>
  <summary><b>Windows</b></summary>

  Available via [Scoop](https://scoop.sh). To install:

  ```powershell
  scoop bucket add supabase https://github.com/supabase/scoop-bucket.git
  scoop install supabase
  ```

  To upgrade:

  ```powershell
  scoop update supabase
  ```
</details>

<details>
  <summary><b>Linux</b></summary>

  Available via [Homebrew](https://brew.sh) and Linux packages.

  #### via Homebrew

  To install:

  ```sh
  brew install supabase/tap/supabase
  ```

  To upgrade:

  ```sh
  brew upgrade supabase
  ```

  #### via Linux packages

  Linux packages are provided in [Releases](https://github.com/supabase/cli/releases). To install, download the `.apk`/`.deb`/`.rpm`/`.pkg.tar.zst` file depending on your package manager and run the respective commands.

  ```sh
  sudo apk add --allow-untrusted <...>.apk
  ```

  ```sh
  sudo dpkg -i <...>.deb
  ```

  ```sh
  sudo rpm -i <...>.rpm
  ```

  ```sh
  sudo pacman -U <...>.pkg.tar.zst
  ```
</details>

<details>
  <summary><b>Other Platforms</b></summary>

  You can also install the CLI via [go modules](https://go.dev/ref/mod#go-install) without the help of package managers.

  ```sh
  go install github.com/supabase/cli@latest
  ```

  Add a symlink to the binary in `$PATH` for easier access:

  ```sh
  ln -s "$(go env GOPATH)/bin/cli" /usr/bin/supabase
  ```

  This works on other non-standard Linux distros.
</details>

<details>
  <summary><b>Community Maintained Packages</b></summary>

  Available via [pkgx](https://pkgx.sh/). Package script [here](https://github.com/pkgxdev/pantry/blob/main/projects/supabase.com/cli/package.yml).
  To install in your working directory:

  ```bash
  pkgx install supabase
  ```

  Available via [Nixpkgs](https://nixos.org/). Package script [here](https://github.com/NixOS/nixpkgs/blob/master/pkgs/development/tools/supabase-cli/default.nix).
</details>

### Run the CLI

```bash
supabase bootstrap
```

Or using npx:

```bash
npx supabase bootstrap
```

The bootstrap command will guide you through the process of setting up a Supabase project using one of the [starter](https://github.com/supabase-community/supabase-samples/blob/main/samples.json) templates.

## Docs

Command & config reference can be found [here](https://supabase.com/docs/reference/cli/about).

## Breaking changes

We follow semantic versioning for changes that directly impact CLI commands, flags, and configurations.

However, due to dependencies on other service images, we cannot guarantee that schema migrations, seed.sql, and generated types will always work for the same CLI major version. If you need such guarantees, we encourage you to pin a specific version of CLI in package.json.

## Developing

To run from source:

```sh
# Go >= 1.22
go run . help
```
