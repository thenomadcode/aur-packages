"""Run the actual PKGBUILD against small Git histories."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PackageVersionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.src = Path(self.tmp.name)
        self.repo = self.src / 'orca'
        self.repo.mkdir()
        self.git('init', '-q')
        self.git('config', 'user.name', 'Test')
        self.git('config', 'user.email', 'test@example.invalid')
        self.commit()

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.repo, text=True).strip()

    def commit(self):
        self.git('commit', '--allow-empty', '-qm', 'fixture')

    def version(self):
        env = dict(os.environ, srcdir=str(self.src))
        return subprocess.check_output(
            ['bash', '-ec', 'source "$1"; pkgver', 'test',
             str(ROOT / 'stably-orca-git/PKGBUILD')], env=env, text=True)

    def test_mobile_and_prerelease_tags_do_not_replace_desktop_release(self):
        self.git('tag', 'v1.4.201')
        for tag in ['mobile-android-v0.0.44', 'v1.4.202-rc.1', 'v1.4.203extra']:
            self.commit()
            self.git('tag', tag)
            with self.subTest(tag=tag):
                self.assertRegex(self.version(), r'^1\.4\.201\.r[0-9]+\.g[0-9a-f]+$')

    def test_no_stable_release_uses_zero_prefix(self):
        self.git('tag', 'mobile-android-v0.0.44')
        self.assertRegex(self.version(), r'^0\.r1\.g[0-9a-f]+$')

    def test_new_desktop_release_is_used(self):
        self.git('tag', 'v1.4.201')
        self.commit()
        self.git('tag', 'v1.4.202')
        self.assertRegex(self.version(), r'^1\.4\.202\.r2\.g[0-9a-f]+$')


if __name__ == '__main__':
    unittest.main()
