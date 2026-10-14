import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('installer', ROOT / 'install.py')
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for name in app.RELEASE_FILES:
            (self.root / name).parent.mkdir(parents=True, exist_ok=True)
            (self.root / name).write_bytes((ROOT / name).read_bytes())
        self.checksums()

    def checksums(self):
        (self.root / 'SHA256SUMS').write_text(''.join(
            hashlib.sha256((self.root / n).read_bytes()).hexdigest() + '  ' + n + '\n'
            for n in app.RELEASE_FILES), encoding='utf-8')

    def initialize(self):
        app.initialize(self.root, 'admin', 'admin@example.com', 8080)

    def test_bundle_verified(self):
        self.assertEqual(app.verify_bundle(self.root)['release'], 'RELEASE_v1.0.2')

    def test_windows_junction_without_pathlib_helper_rejected(self):
        path = SimpleNamespace(is_symlink=lambda: False,
            lstat=lambda: SimpleNamespace(st_reparse_tag=0xA0000003))
        self.assertTrue(app.is_link(path))

    def test_shared_windows_acl_rejected(self):
        self.assertRaises(app.InstallError, app.validate_windows_acl,
            {'owner': 'S-1-5-21-1', 'protected': True, 'allowSids': ['S-1-1-0']}, 'S-1-5-21-1')

    def test_private_windows_acl_accepted(self):
        app.validate_windows_acl({'owner': 'S-1-5-21-1', 'protected': True,
            'allowSids': ['S-1-5-21-1', 'S-1-5-18']}, 'S-1-5-21-1')

    def test_forwarded_headers_not_trusted(self):
        config = (self.root / 'nginx.conf').read_text()
        self.assertIn('proxy_set_header Forwarded "";', config)
        self.assertIn('proxy_set_header X-Forwarded-Prefix "";', config)

    def test_tampered_compose_rejected(self):
        (self.root / 'compose.yml').write_text('changed')
        self.assertRaises(app.InstallError, app.verify_bundle, self.root)

    def test_checksum_traversal_rejected(self):
        with (self.root / 'SHA256SUMS').open('a') as f:
            f.write('0' * 64 + '  ../secret\n')
        self.assertRaises(app.InstallError, app.verify_bundle, self.root)

    def test_manifest_moving_tag_rejected(self):
        p = self.root / 'release.json'
        m = json.loads(p.read_text())
        m['images']['backend-api'] = 'ghcr.io/owner/api:latest'
        p.write_text(json.dumps(m))
        self.checksums()
        self.assertRaises(app.InstallError, app.verify_bundle, self.root)

    def test_init_creates_unique_secrets_and_no_license(self):
        self.initialize()
        env = app.read_env(self.root)
        self.assertEqual(env['REPLAYGUARD_LICENSE_KEY'], '')
        self.assertEqual(len({env[k] for k in app.SECRETS}), 4)
        self.assertEqual(len(app.base64.b64decode(env['REPLAYGUARD_PROFILE_ENCRYPTION_KEY'])), 32)
        self.assertTrue((self.root / 'kafka-secrets').is_dir())

    def test_init_does_not_overwrite(self):
        self.initialize()
        before = (self.root / '.env').read_bytes()
        self.assertRaises(app.InstallError, self.initialize)
        self.assertEqual(before, (self.root / '.env').read_bytes())

    def test_identity_newline_rejected(self):
        self.assertRaises(app.InstallError, app.initialize, self.root, 'admin', 'a@b.com\nKEY=bad', 8080)
        self.assertFalse((self.root / '.env').exists())

    def test_invalid_port_rejected(self):
        self.assertRaises(app.InstallError, app.initialize, self.root, 'admin', 'a@b.com', 0)

    def test_placeholders_rejected(self):
        (self.root / '.env').write_bytes((ROOT / '.env.example').read_bytes())
        self.assertRaises(app.InstallError, app.read_env, self.root)

    def test_duplicate_env_rejected(self):
        self.initialize()
        with (self.root / '.env').open('a') as f:
            f.write('POSTGRES_USER=other\n')
        self.assertRaises(app.InstallError, app.read_env, self.root)

    def test_unsafe_env_rejected(self):
        self.initialize()
        with (self.root / '.env').open('a') as f:
            f.write('COMPOSE_FILE=evil.yml\n')
        self.assertRaises(app.InstallError, app.read_env, self.root)

    def test_wrong_encryption_key_rejected(self):
        self.initialize()
        p = self.root / '.env'
        p.write_text(p.read_text().replace(app.read_env(self.root)['REPLAYGUARD_PROFILE_ENCRYPTION_KEY'], 'invalid'))
        self.assertRaises(app.InstallError, app.read_env, self.root)

    def test_commands_use_explicit_project_and_file(self):
        self.initialize()
        with patch.object(app, 'run', return_value='linux/amd64') as run:
            app.operate(self.root, 'stop')
        args = run.call_args.args[0]
        self.assertIn('--project-name', args)
        self.assertEqual(args[-1], 'stop')
        self.assertNotIn('--volumes', args)

    def test_start_failure_does_not_continue(self):
        self.initialize()
        def fake(args, **kwargs):
            if args[-1] == 'pull':
                raise app.InstallError('pull failed')
            return 'linux/amd64'
        with patch.object(app, 'run', side_effect=fake) as run:
            self.assertRaises(app.InstallError, app.operate, self.root, 'start')
        self.assertFalse(any('up' in c.args[0] for c in run.call_args_list))

    def test_wrong_architecture_stops(self):
        self.initialize()
        with patch.object(app, 'run', return_value='linux/arm64') as run:
            self.assertRaises(app.InstallError, app.operate, self.root, 'start')
        self.assertFalse(any('pull' in c.args[0] for c in run.call_args_list))

    def test_port_conflict_stops_before_pull(self):
        self.initialize()
        def fake(args, **kwargs):
            return '' if 'ps' in args else 'linux/amd64'
        with patch.object(app, 'run', side_effect=fake) as run, patch.object(app.socket, 'socket') as sock:
            sock.return_value.__enter__.return_value.bind.side_effect = OSError('occupied')
            self.assertRaises(app.InstallError, app.operate, self.root, 'start')
        self.assertFalse(any('pull' in c.args[0] for c in run.call_args_list))

    def test_low_disk_stops_before_pull(self):
        self.initialize()
        with patch.object(app, 'run', return_value='linux/amd64') as run, patch.object(app.shutil, 'disk_usage', return_value=Mock(free=0)):
            self.assertRaises(app.InstallError, app.operate, self.root, 'start')
        self.assertFalse(any('pull' in c.args[0] for c in run.call_args_list))

    def test_shell_not_used_and_errors_redacted(self):
        with patch.object(app.subprocess, 'run', return_value=Mock(returncode=1, stdout='secret-value', stderr='secret-value')) as child:
            with self.assertRaises(app.InstallError) as error:
                app.run(['docker', 'compose', 'ps'])
        self.assertNotIn('secret-value', str(error.exception))
        self.assertFalse(child.call_args.kwargs.get('shell', False))

    def test_release_images_present_in_compose(self):
        m = app.verify_bundle(self.root)
        compose = (self.root / 'compose.yml').read_text()
        for image in m['images'].values():
            self.assertIn(image, compose)
        self.assertEqual(compose.count('ports:'), 1)
        self.assertIn('127.0.0.1:', compose)


class PublishedBundleTests(unittest.TestCase):
    def test_shipped_checksums_are_current(self):
        app.verify_bundle(ROOT)


if __name__ == '__main__':
    unittest.main()
