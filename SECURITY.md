# Security

Privately report suspected vulnerabilities to **ravitheja.vkota@replayguard.in**, subject `ReplayGuard security report`. Include affected version, impact, minimal reproduction and a safe contact address. Do not publicly disclose customer information or exploitation details before coordinated review. An acknowledgement or resolution timeline is not guaranteed.

Test only systems you own or are explicitly authorized to assess. Do not access others' data, disrupt shared infrastructure or attempt to obtain signing keys. No paid bounty is promised.

The installation defaults to localhost-only HTTP. Shared deployments require HTTPS, trusted ingress configuration, least-privilege Kafka credentials, restricted host/database access, backups and maintained dependencies. Docker administrators can inspect container configuration; a private env is not a defense against a compromised host administrator.

Keep the profile encryption key and issued license tokens private. The vendor signing key is never part of an installation. Treat unexpected requests to install a signing key or disable signature verification as suspicious.

Use official versioned releases and pinned digests. Local checksums detect changed files but do not authenticate a compromised download source. Do not regard this release as vulnerability-free or penetration-test certified. Read release notices and apply reviewed security updates.
