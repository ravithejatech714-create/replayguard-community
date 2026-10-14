# Installation and Configuration

## Prerequisites

Docker Engine/Desktop with Compose v2 supporting `up --wait`, Linux amd64 containers, and network access to GHCR and your Kafka brokers. Python 3.10+ is required only for the optional installer. Native ARM deployment is not validated for this release. Kafka is supplied by you; the bundle starts PostgreSQL, API, worker, frontend and reverse proxy. Redis is not required.

Use a dedicated directory and persistent storage. Capacity depends on workload and retained history; measure your environment rather than assuming a production sizing guarantee. Verify the release archive checksum against its official release announcement before extraction.

## Recommended Local Setup

Run `python install.py init --admin-email you@example.com` once. Optional flags: `--admin-user admin` and `--port 8080`. It generates separate random passwords/keys and a unique stable Compose project name. It writes `.env` with owner-only access on Unix or a user-specific Windows ACL. A permission failure stops setup; an empty `.env` may remain and needs local review before retrying.

Run `python install.py start`. This verifies pinned references and local checksums, pulls images, starts services and waits for Compose readiness. It never rebuilds images. Open the reported localhost URL. Your initial login is the username supplied during init and password stored privately in `.env`. Complete the password change.

The helper also checks private permissions on an existing `.env`, rejects symlink/junction paths, checks for an occupied localhost port, and requires at least 100 MiB of free space in the installation directory. That small preflight is not a Docker storage or production capacity estimate; reserve and monitor enough Docker/database storage for your workload separately. On Windows, the helper uses built-in Windows PowerShell and ACL utilities. On macOS, install into a real directory rather than a symlinked path.

No database, API, worker or frontend host ports are published. The proxy listens on 127.0.0.1 only. If the port is occupied, choose a different port in `.env`; do not stop unrelated services. Retain the project name on all subsequent starts to reconnect to the same database volume.

## Manual Setup Without Python

Copy `.env.example` to `.env` locally, replace every placeholder, create a `kafka-secrets` directory, and protect `.env` with owner-only file permissions. Use a password manager to generate separate passwords/JWT secret of at least 32 characters. The profile encryption key must be Base64 encoding of exactly 32 cryptographically random bytes. It is not the same as the JWT secret.

On Linux/macOS, use `chmod 600 .env` and ensure the installing account owns it. On Windows, use the file's Security settings to disable inherited access and retain only the owning account plus authorized SYSTEM/Administrators entries. The helper fails closed if it cannot verify this. Do not weaken file permissions to get past an error.

For compatibility with the helper, use values without quotes, `$`, backticks or newlines; the generated random values already satisfy this. Select a unique lowercase project name for an independent installation. Never put a vendor signing private key in the deployment.

```text
docker compose --env-file .env -f compose.yml config --quiet
docker compose --env-file .env -f compose.yml pull
docker compose --env-file .env -f compose.yml up -d --wait --wait-timeout 240
docker compose --env-file .env -f compose.yml ps
```

Run each command separately and stop on error. Shell variables can override `.env` in manual Compose. Clear stale Compose/application variables first. Unlike the helper, manual Compose does not enforce placeholder rejection or minimum secret length. Never share plain `docker compose config` or `docker inspect` output: it may contain secrets.

## Safe Configuration Surface

The public example exposes only these settings. Extra entries in `.env` are not automatically passed to containers. The helper rejects unknown variables; this is intentional.

| Variables | Purpose / sensitivity |
| --- | --- |
| `REPLAYGUARD_PROJECT_NAME` | Stable unique installation identity; changing it selects different Compose resources |
| `REPLAYGUARD_HTTP_PORT` | Localhost port, 1024-65535 |
| `POSTGRES_DB`, `POSTGRES_USER` | Database initialization names |
| `POSTGRES_PASSWORD` | Private random database password; env edits do not change an existing DB password |
| `REPLAYGUARD_ADMIN_USERNAME`, `REPLAYGUARD_ADMIN_EMAIL`, `REPLAYGUARD_ADMIN_DISPLAY_NAME` | Initial administrator identity |
| `REPLAYGUARD_ADMIN_PASSWORD` | Private bootstrap password; changing env does not reset an existing user's password |
| `REPLAYGUARD_JWT_SECRET` | Private session-signing secret |
| `REPLAYGUARD_PROFILE_ENCRYPTION_KEY` | Private encryption key; back it up and retain across restarts/upgrades |
| `REPLAYGUARD_LICENSE_KEY` | Empty for Community; confidential issued token for evaluation/paid use |

Images are fixed by digest in `compose.yml` and documented in `release.json`, not overrideable through `.env`. Do not independently substitute `latest`. TLS, log verbosity, webhook and insecure-authentication controls are not user-tunable helper flags. Webhooks and insecure SASL/PLAIN are disabled. Policy settings cannot raise edition limits.

## Kafka Networking and Certificates

Both API and worker must reach bootstrap AND advertised broker addresses. `localhost` in a container is not the host Kafka broker. For host Kafka, configure a suitable host-gateway address and matching reachable advertised listeners. For Kafka in a separate Compose project, attach an explicitly reviewed shared network to both services using a manual deployment configuration. The unmodified helper intentionally does not add arbitrary networks.

For SSL/SASL_SSL profiles, put your truststore and any required client certificate files in `kafka-secrets`. Both services mount it read-only at `/etc/replayguard/kafka`. Use that container path in the UI, for example `/etc/replayguard/kafka/client.truststore.jks`, with the actual store type/password. Ensure service UID 10001 can read required files; do not make them publicly writable. Never commit this directory.

Prefer TLS with least-privilege Kafka credentials. Keep hostname verification enabled. Do not resolve TLS failures by disabling verification or permitting cleartext SASL/PLAIN.

## Shared HTTPS Deployment

The supplied configuration is NOT suitable for remote users unchanged. Contact support for reviewed TLS/ingress setup. You must configure a valid certificate and hostname, Secure authentication cookies, the exact HTTPS browser origin, trusted forwarded-header handling and restricted direct access. Do not merely change 127.0.0.1 to 0.0.0.0 or assume an HTTPS URL configures TLS.

A custom Compose/proxy file invalidates the helper checksum check. Use manual Compose for intentionally reviewed customized deployments and retain the original release separately. Do not regenerate checksums merely to silence an unexplained modification.

See [Docker environment interpolation](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/) and [image digest pinning](https://docs.docker.com/reference/cli/docker/image/pull/).
