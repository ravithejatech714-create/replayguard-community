# First Recovery and Operations

## First Replay

1. Log in, change the bootstrap password and confirm Community edition and worker health.
2. Create and test one Kafka profile. Inspect a non-production source topic and a separate destination topic on that profile.
3. Configure one enabled policy permitting those topics. Set the needed approval rules; a second authorized user may be needed for independent approval.
4. Choose offset-range recovery and a small retained range, such as partition 0, start 0 and end 10. Start is inclusive, end exclusive; first confirm those offsets exist. Set 5 records/second.
5. Preview and address blockers. Run a dry run. It reads/scans according to the operation but does not publish destination records or spend a monthly execution.
6. Create/approve the actual replay, monitor progress and verify records in the destination. Check downstream processing independently.

Rate is a ceiling, not a throughput guarantee. Kafka latency, transactions, source availability and system load can lower actual throughput. Requested spans are not guaranteed record counts because offsets may have gaps. Duplicates can occur around failures; design downstream handling accordingly.

## Pause, Stop and Resume

Use the application's authorized controls to pause/stop a job. Inspect failure details before Retry; Rerun creates a new job and consumes a new monthly credit when started. Retries remain subject to attempt limits, unchanged approved routes, expiry and safety checks. A failure does not undo records already published.

To stop the local installation without deleting data:
```text
python install.py stop
```
To restart:
```text
python install.py start
```

Do not use volume deletion/pruning to restart. Never run `down --volumes` against a retained deployment. Back up PostgreSQL and the profile encryption key together, plus configuration and certificate material. Use a consistent PostgreSQL backup/restore procedure, encrypt backup storage, and test recovery. Copying an actively written database directory is not a reliable backup.

## Evaluation or Paid Upgrade

Email [ravitheja.vkota@replayguard.in](mailto:ravitheja.vkota@replayguard.in). After receiving a license, first pause/finish active work and back up. Stop API and worker together, update `REPLAYGUARD_LICENSE_KEY` privately, then recreate both with the same token:

```text
docker compose --env-file .env -f compose.yml stop backend-api replay-worker
docker compose --env-file .env -f compose.yml up -d --force-recreate backend-api replay-worker
docker compose --env-file .env -f compose.yml up -d --force-recreate reverse-proxy
```

Recreate the proxy after the API is healthy so it resolves the replacement API container's address. Stop on command failure and inspect local diagnostics before continuing.

Confirm consistent edition/worker diagnostics before executing. No new database is required. An invalid license is rejected, not converted into unrestricted access. On intentional downgrade, correct excess active users/profiles/policies; paid-only queued work must not execute in Community. Discuss partially completed work with support before downgrading.

## Version Upgrades

There is no automatic update. Obtain a new official versioned bundle, review migration notes, back up, and preserve the existing private configuration/project name and encryption key. Follow that release's upgrade procedure; do not run its `init` against an existing env. Update all components together. Older application images may not support a newer database schema, so an image-only rollback is not automatically safe. Never overwrite the existing installation as a troubleshooting shortcut.

## Troubleshooting

| Problem | Action |
| --- | --- |
| Pull fails | Check registry reachability and architecture; these packages support anonymous pull |
| Local port in use | Change `REPLAYGUARD_HTTP_PORT` in `.env`; do not stop unrelated services |
| Backend unhealthy | Inspect local API/PostgreSQL logs; check migrations, disk and configuration |
| Kafka fails | Check advertised addresses, firewall, authentication and mounted certificates on API AND worker |
| Community resource warning | Retain at most two active users, one enabled profile and one enabled policy |
| Job waits for allowance | Check UTC monthly usage, approval and execution-window validity |
| Old initial password no longer works | Use the changed password; env does not reset an existing user |
| Release checksum fails | Obtain trusted unmodified files or use a reviewed manual configuration; do not bypass blindly |
| Permission failure during init | Review local file ACLs; an empty env may need removal after confirming it contains no configuration |

Inspect `docker compose --env-file .env -f compose.yml logs --tail=100 backend-api replay-worker` locally. Redact credentials, tokens, payloads, infrastructure addresses and personal information before sending diagnostics. Do not expose management or database ports publicly to troubleshoot.
