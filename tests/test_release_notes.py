"""Public release pages must lead with a working, version-specific download."""
import unittest
from tools.release_notes import render


class ReleaseNotes(unittest.TestCase):
    def test_dual_platform_downloads_and_signing_limit_precede_current_notes_but_old_releases_stay_windows_only(self):
        body=render('0.4.0','## v0.4.0\nCurrent release detail\n\n## v0.3.68\nOld detail\n')
        for suffix in ('windows-x64.zip','macos-arm64.zip','macos-arm64.dmg'):
            self.assertLess(body.index('LMU-Stintrix-v0.4.0-'+suffix),body.index('Current release detail'))
        self.assertIn('SHA256SUMS.txt',body);self.assertIn('not notarized',body);self.assertNotIn('Old detail',body)
        self.assertNotIn('macos-arm64',render('0.3.68','## v0.3.68\nPrevious release\n'))

    def test_download_precedes_only_requested_version_and_links_to_full_history(self):
        history='Preamble\n## v1.2.4 — New\n\nNewer\n\n## v1.2.3 — Current\n\nCurrent detail\n\n### More\n\nMore detail\n\n## v1.2.2 — Old\n\nOlder\n'
        body=render('1.2.3',history)
        asset='https://github.com/MarkYang44/LMU-Stintrix/releases/download/v1.2.3/LMU-Stintrix-v1.2.3-windows-x64.zip'
        self.assertLess(body.index(asset),body.index('Current detail'))
        self.assertIn('More detail',body);self.assertNotIn('Newer',body);self.assertNotIn('Older',body);self.assertNotIn('Preamble',body)
        self.assertIn('/blob/v1.2.3/docs/RELEASE_NOTES.md',body)
        self.assertIn('`data/`',body);self.assertIn('`local_settings.json`',body)
        self.assertEqual(render('1.2.3','## v1.2.3\r\nLast section\r\n').count('Last section'),1)

    def test_missing_or_malformed_version_never_publishes_the_whole_history(self):
        for version in ('1.2.3','v1.2.3','1.2.3/path','1.2.3\n'):
            with self.subTest(version=version),self.assertRaises(ValueError):render(version,'## v1.2.30\nUnrelated history\n')
