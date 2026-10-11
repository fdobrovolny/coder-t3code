"""Exercise the Terraform-rendered scripts with isolated fake executables."""
import base64
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Scripts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / '.local/bin'
        self.bin.mkdir(parents=True)
        self.workdir = self.root / "project with 'quotes'"
        self.workdir.mkdir()
        self.env = dict(os.environ, PATH=f'{self.bin}:/usr/bin:/bin', TEST_ROOT=str(self.root))

    def executable(self, name, body):
        p = self.bin / name
        p.write_text('#!/bin/bash\nset -eu\n' + body)
        p.chmod(0o755)

    def render(self, name, **args):
        values = dict(ARG_WORKDIR=base64.b64encode(str(self.workdir).encode()).decode(), **args)
        expr = f'templatefile("{ROOT}/scripts/{name}.sh.tftpl", {json.dumps(values)})'
        result = subprocess.run(['terraform', 'console'], cwd=ROOT, input=f'jsonencode({expr})\n',
                                text=True, capture_output=True, check=True)
        script = json.loads(json.loads(result.stdout))
        # Isolate paths without altering the process HOME or shell profiles.
        script = script.replace('${HOME}', str(self.root))
        p = self.root / f'{name}.sh'
        p.write_text(script)
        subprocess.run(['bash', '-n', str(p)], check=True)
        return p

    def run_script(self, script):
        return subprocess.run(['bash', str(script)], env=self.env, capture_output=True,
                              text=True, timeout=10)

    def test_existing_pinned_install_and_path_link(self):
        self.executable('t3', 'test "$1" = --version\necho "t3 v0.0.42"\n')
        self.executable('curl', 'exit 99\n')
        self.env['CODER_SCRIPT_BIN_DIR'] = str(self.root / 'coder-bin')
        script = self.render('install', ARG_INSTALL_T3CODE='true',
                             ARG_T3CODE_VERSION=base64.b64encode(b'0.0.42').decode())
        result = self.run_script(script)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.root / 'coder-bin/t3').is_symlink())

    def test_existing_latest_install_updates(self):
        self.executable('t3', '''case "$1" in
  --version) echo "t3 v0.0.42" ;;
  update) touch "$TEST_ROOT/updated" ;;
  *) exit 99 ;;
esac
''')
        self.executable('curl', 'exit 99\n')
        script = self.render('install', ARG_INSTALL_T3CODE='true',
                             ARG_T3CODE_VERSION=base64.b64encode(b'latest').decode())
        result = self.run_script(script)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.root / 'updated').exists())

    def test_existing_disabled_install_skips_update(self):
        self.executable('t3', 'test "$1" = --version\necho "t3 v0.0.42"\n')
        self.executable('curl', 'exit 99\n')
        script = self.render('install', ARG_INSTALL_T3CODE='false',
                             ARG_T3CODE_VERSION=base64.b64encode(b'latest').decode())
        result = self.run_script(script)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_disabled_install_fails(self):
        script = self.render('install', ARG_INSTALL_T3CODE='false',
                             ARG_T3CODE_VERSION=base64.b64encode(b'latest').decode())
        result = self.run_script(script)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('not installed', result.stderr)

    def test_start_and_duplicate_start(self):
        self.executable('t3', 'touch "$TEST_ROOT/ready"\nexec sleep 30\n')
        self.executable('curl', 'test -f "$TEST_ROOT/ready"\n')
        script = self.render('start', ARG_WEB_PORT='3773')
        pidfile = self.root / '.coder-modules/fdobrovolny/t3code/server.pid'
        try:
            result = self.run_script(script)
            self.assertEqual(result.returncode, 0, result.stderr)
            pid = pidfile.read_text()
            result = self.run_script(script)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('already running', result.stdout)
            self.assertEqual(pidfile.read_text(), pid)
            log = pidfile.parent / 'logs/server.log'
            self.assertEqual(log.stat().st_mode & 0o777, 0o600)
        finally:
            if pidfile.exists():
                try:
                    os.kill(int(pidfile.read_text()), signal.SIGTERM)
                except ProcessLookupError:
                    pass

    def test_occupied_port_rejected(self):
        self.executable('curl', 'exit 0\n')
        result = self.run_script(self.render('start', ARG_WEB_PORT='3773'))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('already serving', result.stderr)

    def test_early_exit_reported(self):
        self.executable('curl', 'exit 7\n')
        self.executable('t3', 'exit 42\n')
        result = self.run_script(self.render('start', ARG_WEB_PORT='3773'))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('server exited', result.stderr)
        self.assertFalse((self.root / '.coder-modules/fdobrovolny/t3code/server.pid').exists())


if __name__ == '__main__':
    unittest.main()
