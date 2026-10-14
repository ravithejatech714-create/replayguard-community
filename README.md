# ReplayGuard Community

Controlled Kafka recovery, in your own environment.

ReplayGuard helps engineers inspect Kafka data, preview recovery scope, apply recovery policies and approvals, and replay selected records with a configured rate and execution history. Community provides a free, bounded way to try this workflow on your own Kafka cluster.

**Release:** `RELEASE_v1.0.2` | **Platform:** Linux containers on amd64 | **Deployment:** Docker Compose

This repository contains installation tooling and documentation, not ReplayGuard application source code. Community is proprietary software provided without a license fee, not an open-source edition. Installation and use are subject to the [Community usage terms](TERMS.md).

## Start Here

Install Docker with Compose v2 and Python 3.10 or newer. Download this versioned repository/release from the official ReplayGuard distribution channel, extract it, and open a terminal in this directory. Docker must be running Linux amd64 containers. No GitHub sign-in is required to pull the public images.

```text
python install.py verify
python install.py init --admin-email you@example.com
python install.py start
python install.py status
```

Use `python3` on systems where that is the Python 3 command. Open **http://localhost:8080**. Retrieve the generated initial administrator password by viewing your private `.env` locally, then change it at first login. The installer never prints secrets. This is a localhost-only evaluation configuration, not an internet-facing HTTPS deployment.

The installer verifies local checksums and pins image digests. It does not install Docker, update automatically, overwrite an existing `.env`, or delete data. Checksums are not proof of publisher identity: obtain this entire bundle through the trusted official release channel.

- [Installation, configuration and manual Compose setup](docs/installation.md)
- [First recovery, operations, upgrades and troubleshooting](docs/operations.md)
- [Support and evaluation/paid plans](SUPPORT.md)
- [Security reporting and deployment responsibilities](SECURITY.md)
- [Third-party components](THIRD_PARTY_NOTICES.md)

## Community Allowances

| Capability | Included |
| --- | --- |
| Active users, including administrator | 2 |
| Enabled Kafka profiles / recovery policies | 1 / 1 |
| Recovery | Offset-range replay between different topics on one profile |
| Combined requested offset span | 1,000 per job across selected partitions |
| Record / output-byte reservation budget | 1,000 / 10 MiB per job |
| Configured rate | 1-25 records/second |
| Concurrent execution, including dry runs | 1 |
| New actual executions | 5 per UTC calendar month |
| Dry runs | No monthly execution charge; other limits still apply |

Inspection, history and authorized pause/stop controls remain available. Governance and Kafka permissions still apply. Community has no expiry date; it retains the stated limits. An actual execution spends a credit when it starts; failures/stops do not refund it. Eligible retry/resume of that job does not spend another credit, while rerun creates a new job. Byte/record reservations from failed attempts can reduce the remaining retry budget. Once exhausted, new executions wait subject to approval and execution-window validity.

## Need More?

Contact **[ravitheja.vkota@replayguard.in](mailto:ravitheja.vkota@replayguard.in)** for evaluation or paid access to larger allowances, timestamp-window recovery, DLQ redrive, same-topic or cross-profile replay, consumer-group offset reset, and service-account/agent proposals. Plans retain their own limits and safety controls. You can retain your database and history when upgrading.

Kafka recovery can affect downstream applications. Begin with non-production topics, preview carefully, maintain backups and ensure consumers handle duplicates. A completed replay does not prove successful downstream business processing.
