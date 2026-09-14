"""Exercise workflow shell steps against local HTTP and version fixtures."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]


class DownloadHandler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.send_response(200 if self.path == '/available' else 404)
        self.end_headers()

    def log_message(self, *args):
        pass


class WorkflowTests(unittest.TestCase):
    def step(self, name):
        workflow = yaml.safe_load((ROOT / '.github/workflows/update-stably-orca-bin.yml').read_text())
        matches = [s for s in workflow['jobs']['update']['steps'] if s['name'] == name]
        self.assertEqual(len(matches), 1, f'Missing workflow step: {name}')
        return matches[0]

    def test_unchanged_release_download_is_checked(self):
        step = self.step('Check upstream download')
        # This check must run even when Compare versions finds no update.
        self.assertNotIn('if', step)
        server = ThreadingHTTPServer(('127.0.0.1', 0), DownloadHandler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        for path, success in [('/available', True), ('/removed', False)]:
            with self.subTest(path=path):
                env = dict(os.environ, DOWNLOAD_URL=f'http://127.0.0.1:{server.server_port}{path}')
                result = subprocess.run(['bash', '-e', '-c', step['run']], env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode == 0, success, result.stderr)

    def test_withdrawn_release_can_roll_back(self):
        with tempfile.NamedTemporaryFile() as output:
            env = dict(os.environ, CUR='1.4.202', CUR_FULL='1.4.202-1', NEW='1.4.201',
                       AUR_PUBLISHED='1.4.202-1', FORCE='false', GITHUB_OUTPUT=output.name)
            subprocess.run(['bash', '-e', '-c', self.step('Compare versions')['run']],
                           env=env, check=True, capture_output=True)
            values = dict(line.split('=', 1) for line in Path(output.name).read_text().splitlines())
            self.assertEqual(values['changed'], 'true')
            self.assertEqual(values['needs_bump'], 'true')


if __name__ == '__main__':
    unittest.main()
