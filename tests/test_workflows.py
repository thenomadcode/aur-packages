"""Exercise workflow shell steps against local HTTP and version fixtures."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
import re
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
        base = f'http://127.0.0.1:{server.server_port}'
        # (x86_64 path, aarch64 path, expected success, expected missing list)
        cases = [
            ('/available', '/available', True, ''),
            ('/removed', '/available', False, 'x86_64'),
            ('/available', '/removed', False, 'aarch64'),
            ('/removed', '/removed', False, 'x86_64 aarch64'),
        ]
        for x86, arm, success, missing in cases:
            with self.subTest(x86_64=x86, aarch64=arm), tempfile.NamedTemporaryFile() as output:
                env = dict(os.environ, DOWNLOAD_URL_X86_64=base + x86,
                           DOWNLOAD_URL_AARCH64=base + arm, GITHUB_OUTPUT=output.name)
                result = subprocess.run(['bash', '-e', '-c', step['run']], env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode == 0, success, result.stderr)
                self.assertEqual(Path(output.name).read_text().strip(), f'missing={missing}')

    def test_every_pkgbuild_arch_has_a_download_check(self):
        env = self.step('Check upstream download')['env']
        pkgbuild = (ROOT / 'stably-orca-bin/PKGBUILD').read_text()
        arches = re.search(r"^arch=\(([^)]*)\)", pkgbuild, re.M).group(1).replace("'", '').split()
        self.assertEqual(sorted(arches), ['aarch64', 'x86_64'])
        for arch in arches:
            self.assertIn(f'DOWNLOAD_URL_{arch.upper()}', env)

    def run_sum_check(self, srcinfo, digests=None):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / 'SRCINFO').write_text(srcinfo)
            env = dict(os.environ)
            if digests is None:
                env['SKIP_DIGEST_LOOKUP'] = '1'
            else:
                gh = directory / 'gh'
                gh.write_text('#!/bin/sh\nprintf "%s\\n" "$DIGESTS"\n')
                gh.chmod(0o755)
                env.update(PATH=f'{directory}:{env["PATH"]}', DIGESTS=digests)
            return subprocess.run(['bash', str(ROOT / '.github/scripts/check-arch-sums.sh'),
                                   str(directory / 'SRCINFO'), 'v1.0.0'],
                                  env=env, capture_output=True, text=True)

    def test_committed_srcinfo_has_both_arch_sums(self):
        result = self.run_sum_check((ROOT / 'stably-orca-bin/.SRCINFO').read_text())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_arch_sum_check_rejects_missing_or_mismatched_sums(self):
        a, b = 'a' * 64, 'b' * 64
        good = f'\tsha256sums_x86_64 = {a}\n\tsha256sums_aarch64 = {b}\n'
        digests = f'orca-linux.AppImage sha256:{a}\norca-linux-arm64.AppImage sha256:{b}'
        self.assertEqual(self.run_sum_check(good, digests).returncode, 0)
        # GitHub omitted the digest: accept the downloaded hash with a warning.
        self.assertEqual(self.run_sum_check(good, 'orca-linux.AppImage \norca-linux-arm64.AppImage ').returncode, 0)
        for srcinfo, digest_text in [
            (f'\tsha256sums_x86_64 = {a}\n', digests),                          # aarch64 missing
            (f'\tsha256sums_x86_64 = {a}\n\tsha256sums_aarch64 = SKIP\n', digests),
            (good, f'orca-linux.AppImage sha256:{a}\norca-linux-arm64.AppImage sha256:{a}'),
        ]:
            with self.subTest(srcinfo=srcinfo, digests=digest_text):
                self.assertNotEqual(self.run_sum_check(srcinfo, digest_text).returncode, 0)

    def test_built_version_check_reads_complete_metadata_stream(self):
        # makepkg writes metadata incrementally. Exiting awk at pkgver can
        # SIGPIPE the producer and fail the pipeline despite a valid version.
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            metadata = re.sub(r'(?m)^(\tpkgver = ).*$', r'\g<1>1.4.163.r10916.g539d4d1f32',
                              (ROOT / 'stably-orca-git/.SRCINFO').read_text())
            (directory / 'metadata').write_text(metadata)
            makepkg = directory / 'makepkg'
            makepkg.write_text('#!/usr/bin/env python3\nimport os, time\n'
                               'from pathlib import Path\n'
                               'for line in Path(os.environ["METADATA"]).read_text().splitlines():\n'
                               '    print(line, flush=True)\n    time.sleep(0.005)\n')
            makepkg.chmod(0o755)
            vercmp = directory / 'vercmp'
            vercmp.write_text('#!/bin/sh\necho 1\n')
            vercmp.chmod(0o755)
            env = dict(os.environ, PATH=f'{directory}:{os.environ["PATH"]}',
                       METADATA=str(directory / 'metadata'))
            result = subprocess.run(['bash', str(ROOT / 'tests/check-built-version.sh')],
                                    env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('1.4.163.r10916.g539d4d1f32', result.stdout)

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
