#!/usr/bin/env python3
"""Explicit, local-only setup for the accompanying versioned Compose release."""
import argparse
import base64
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import stat
import subprocess
import sys

RELEASE_FILES = ('install.py', 'compose.yml', 'nginx.conf', 'release.json', '.env.example',
                 'README.md', 'docs/installation.md', 'docs/operations.md', 'SECURITY.md',
                 'SUPPORT.md', 'TERMS.md', 'THIRD_PARTY_NOTICES.md', '.gitignore',
                 '.gitattributes', 'tests/test_install.py')
SECRETS = ('POSTGRES_PASSWORD', 'REPLAYGUARD_ADMIN_PASSWORD', 'REPLAYGUARD_JWT_SECRET',
           'REPLAYGUARD_PROFILE_ENCRYPTION_KEY')
KEYS = set(SECRETS) | {'POSTGRES_DB', 'POSTGRES_USER', 'REPLAYGUARD_ADMIN_USERNAME',
    'REPLAYGUARD_ADMIN_EMAIL', 'REPLAYGUARD_ADMIN_DISPLAY_NAME', 'REPLAYGUARD_LICENSE_KEY',
    'REPLAYGUARD_HTTP_PORT', 'REPLAYGUARD_PROJECT_NAME'}
SERVICES = ('postgres', 'backend-api', 'replay-worker', 'frontend', 'reverse-proxy')


class InstallError(Exception):
    pass


def is_link(path):
    return (path.is_symlink() or getattr(path, 'is_junction', lambda: False)()
            or getattr(path.lstat(), 'st_reparse_tag', 0) in (0xA0000003, 0xA000000C))


def safe_path(root, relative):
    if relative not in RELEASE_FILES and relative not in ('.env', 'SHA256SUMS', 'kafka-secrets'):
        raise InstallError('Unrecognized release path.')
    path = root / relative
    for part in (root, *path.parents, path):
        if part.exists() or part.is_symlink():
            if is_link(part):
                raise InstallError('Linked installation paths are not supported.')
    return path


def verify_bundle(root):
    lines = safe_path(root, 'SHA256SUMS').read_text(encoding='utf-8').splitlines()
    seen = set()
    for line in lines:
        match = re.fullmatch(r'([0-9a-f]{64})  (.+)', line)
        if not match or match[2] not in RELEASE_FILES or match[2] in seen:
            raise InstallError('Invalid release checksum list.')
        seen.add(match[2])
        if hashlib.sha256(safe_path(root, match[2]).read_bytes()).hexdigest() != match[1]:
            raise InstallError('Release files changed. Use an unmodified official release or manual reviewed setup.')
    if seen != set(RELEASE_FILES):
        raise InstallError('Incomplete release checksum list.')
    manifest = json.loads(safe_path(root, 'release.json').read_text(encoding='utf-8'))
    if manifest.get('release') != 'RELEASE_v1.0.2' or manifest.get('platform') != 'linux/amd64':
        raise InstallError('Unsupported release or architecture.')
    images = manifest.get('images', {})
    if set(images) != set(SERVICES):
        raise InstallError('Incomplete image manifest.')
    compose = safe_path(root, 'compose.yml').read_text(encoding='utf-8')
    for service, image in images.items():
        prefix = 'postgres' if service == 'postgres' else (
            'ghcr.io/ravithejatech714-create/replayguard-community-' + service)
        if not isinstance(image, str) or not re.fullmatch(re.escape(prefix) + r'@sha256:[0-9a-f]{64}', image):
            raise InstallError('Image must use the official repository and an immutable digest.')
        if image not in compose:
            raise InstallError('Compose image does not match the release manifest.')
    return manifest


def run(args, env=None, timeout=600):
    try:
        result = subprocess.run(args, env=env, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise InstallError('Required command unavailable or timed out. Check Docker and retry; no data was deleted.') from error
    if result.returncode:
        # Docker diagnostics may contain interpolated configuration or secrets.
        raise InstallError('Command failed: ' + args[0] + '. Inspect Docker locally; redact diagnostics before sharing.')
    return result.stdout.strip()


def protect_file(path):
    if os.name == 'nt':
        identity = run(['whoami', '/user', '/fo', 'csv', '/nh'])
        rows = list(csv.reader(identity.splitlines()))
        sid = rows[0][-1] if rows else ''
        if not re.fullmatch(r'S-1-[0-9-]+', sid):
            raise InstallError('Unable to identify Windows account for private file permissions.')
        run(['icacls', str(path), '/inheritance:r', '/grant:r', '*' + sid + ':(F)'])
    else:
        path.chmod(0o600)


def validate_windows_acl(acl, sid):
    allowed = acl.get('allowSids', [])
    if isinstance(allowed, str):
        allowed = [allowed]
    if (not sid or acl.get('owner') != sid or not acl.get('protected')
            or not allowed or set(allowed) - {sid, 'S-1-5-18', 'S-1-5-32-544'}):
        raise InstallError('Env permissions are not private. Restrict ownership/access to your account and authorized system administrators.')


def require_private_env(path):
    if os.name != 'nt':
        info = path.stat()
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
            raise InstallError('Env must be owned by this user and private (chmod 600 .env).')
        return
    code = (
        "$ErrorActionPreference='Stop'; $a=Get-Acl -LiteralPath $env:REPLAYGUARD_ENV_CHECK; "
        "$s=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value; "
        "$r=@($a.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]) | "
        "Where-Object {$_.AccessControlType -eq 'Allow'} | ForEach-Object {$_.IdentityReference.Value}); "
        "@{owner=$a.GetOwner([Security.Principal.SecurityIdentifier]).Value; "
        "protected=$a.AreAccessRulesProtected; allowSids=$r; current=$s} | ConvertTo-Json -Compress"
    )
    child_env = dict(os.environ, REPLAYGUARD_ENV_CHECK=str(path))
    # PowerShell 7 module paths cannot be reused by Windows PowerShell 5.1.
    child_env = {k: v for k, v in child_env.items() if k.upper() != 'PSMODULEPATH'}
    try:
        result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', code],
                                capture_output=True, text=True, env=child_env, timeout=30, check=False)
        if result.returncode:
            raise InstallError('Unable to verify private Windows env permissions.')
        acl = json.loads(result.stdout)
        validate_windows_acl(acl, acl.get('current'))
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        raise InstallError('Unable to verify private Windows env permissions.') from error


def initialize(root, username, email, port):
    verify_bundle(root)
    if not re.fullmatch(r'[A-Za-z0-9_.-]{3,50}', username) or not re.fullmatch(r'[A-Za-z0-9_.+%-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', email):
        raise InstallError('Supply a simple administrator username and valid email address.')
    if not 1024 <= port <= 65535:
        raise InstallError('Choose a local port between 1024 and 65535.')
    path = safe_path(root, '.env')
    if path.exists():
        raise InstallError('An .env already exists. It will not be overwritten.')
    secret_dir = safe_path(root, 'kafka-secrets')
    secret_dir.mkdir(exist_ok=True)
    env = {
        'REPLAYGUARD_PROJECT_NAME': 'replayguard-community-' + secrets.token_hex(4),
        'POSTGRES_DB': 'replayguard_community', 'POSTGRES_USER': 'replayguard_community',
        'POSTGRES_PASSWORD': secrets.token_hex(32),
        'REPLAYGUARD_ADMIN_USERNAME': username, 'REPLAYGUARD_ADMIN_EMAIL': email,
        'REPLAYGUARD_ADMIN_DISPLAY_NAME': 'ReplayGuard Administrator',
        'REPLAYGUARD_ADMIN_PASSWORD': 'Rg!' + secrets.token_urlsafe(32),
        'REPLAYGUARD_JWT_SECRET': secrets.token_urlsafe(48),
        'REPLAYGUARD_PROFILE_ENCRYPTION_KEY': base64.b64encode(secrets.token_bytes(32)).decode('ascii'),
        'REPLAYGUARD_LICENSE_KEY': '', 'REPLAYGUARD_HTTP_PORT': str(port),
    }
    # Create exclusively and apply permissions before any secret bytes are written.
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as error:
        raise InstallError('An .env already exists. It will not be overwritten.') from error
    with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as file:
        protect_file(path)
        file.write(''.join(k + '=' + v + '\n' for k, v in env.items()))
    print('Created private .env. View the initial administrator password locally; it is not printed here.')


def read_env(root):
    env = {}
    path = safe_path(root, '.env')
    require_private_env(path)
    for line in path.read_text(encoding='utf-8').splitlines():
        if not line or line.startswith('#'):
            continue
        if '=' not in line:
            raise InstallError('Invalid env format.')
        key, value = line.split('=', 1)
        if key not in KEYS or key in env or 'REPLACE_' in value or not re.fullmatch(r'[A-Za-z0-9_@.!+/%=: -]*', value):
            raise InstallError('Unsupported, duplicate or unsafe env setting. Use the supplied example format.')
        env[key] = value
    if set(env) != KEYS or any(not env[k] for k in KEYS - {'REPLAYGUARD_LICENSE_KEY'}):
        raise InstallError('Missing required configuration.')
    for key in ('POSTGRES_DB', 'POSTGRES_USER', 'REPLAYGUARD_PROJECT_NAME'):
        if not re.fullmatch(r'[a-z][a-z0-9_-]{2,62}', env[key]):
            raise InstallError('Use simple lowercase database and project names.')
    if not re.fullmatch(r'[A-Za-z0-9_.-]{3,50}', env['REPLAYGUARD_ADMIN_USERNAME']):
        raise InstallError('Invalid administrator username.')
    if not re.fullmatch(r'[A-Za-z0-9_.+%-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', env['REPLAYGUARD_ADMIN_EMAIL']):
        raise InstallError('Invalid administrator email.')
    if not env['REPLAYGUARD_HTTP_PORT'].isdigit() or not 1024 <= int(env['REPLAYGUARD_HTTP_PORT']) <= 65535:
        raise InstallError('Invalid local HTTP port.')
    if any(len(env[k]) < 32 for k in SECRETS):
        raise InstallError('Use independently generated strong secrets of at least 32 characters.')
    try:
        if len(base64.b64decode(env['REPLAYGUARD_PROFILE_ENCRYPTION_KEY'], validate=True)) != 32:
            raise ValueError()
    except ValueError as error:
        raise InstallError('Profile encryption key must encode exactly 32 random bytes.') from error
    return env


def operate(root, action):
    verify_bundle(root)
    env = read_env(root)
    safe_path(root, 'kafka-secrets').mkdir(exist_ok=True)
    child_env = {k: v for k, v in os.environ.items() if k not in KEYS and not k.startswith('COMPOSE_')}
    base = ['docker', 'compose', '--project-name', env['REPLAYGUARD_PROJECT_NAME'],
            '--env-file', str(root / '.env'), '-f', str(root / 'compose.yml')]
    if action == 'start':
        platform = run(['docker', 'version', '--format', '{{.Server.Os}}/{{.Server.Arch}}'], env=child_env, timeout=30)
        if platform != 'linux/amd64':
            raise InstallError('This release requires a linux/amd64 Docker engine.')
        run(base + ['version', '--short'], env=child_env, timeout=30)
        run(base + ['config', '--quiet'], env=child_env, timeout=30)
        if shutil.disk_usage(root).free < 100 * 1024 * 1024:
            raise InstallError('Insufficient local free disk space. Also check Docker storage capacity separately.')
        existing = run(base + ['ps', '-q', 'reverse-proxy'], env=child_env, timeout=30)
        if not existing:
            try:
                with socket.socket() as probe:
                    probe.bind(('127.0.0.1', int(env['REPLAYGUARD_HTTP_PORT'])))
            except OSError as error:
                raise InstallError('Local HTTP port is occupied. Choose another port; do not stop unrelated services.') from error
        print('Pulling pinned images. This can take several minutes.')
        run(base + ['pull'], env=child_env)
        run(base + ['up', '-d', '--wait', '--wait-timeout', '240'], env=child_env)
        print('Started. Open http://localhost:' + env['REPLAYGUARD_HTTP_PORT'])
    elif action == 'stop':
        run(base + ['stop'], env=child_env)
        print('Stopped. Containers, configuration and database volume retained.')
    else:
        print(run(base + ['ps'], env=child_env, timeout=30))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    init = sub.add_parser('init', help='Generate a new private local configuration; never overwrite')
    init.add_argument('--admin-user', default='admin')
    init.add_argument('--admin-email', required=True)
    init.add_argument('--port', type=int, default=8080)
    for name in ('start', 'status', 'stop', 'verify'):
        sub.add_parser(name)
    args = parser.parse_args()
    root = Path(__file__).absolute().parent
    try:
        if args.action == 'init':
            initialize(root, args.admin_user, args.admin_email, args.port)
        elif args.action == 'verify':
            verify_bundle(root)
            print('Release checksums and pinned image references verified. This is not a publisher signature check.')
        else:
            operate(root, args.action)
    except (InstallError, OSError, ValueError) as error:
        print('Setup stopped: ' + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
