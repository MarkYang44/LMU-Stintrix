"""Release publication requires matching Windows and Mac assets as one unit."""
import hashlib
import json
from pathlib import Path
import plistlib
import tempfile
import unittest
import zipfile
from tools.release_assets import verify

ROOT=Path(__file__).resolve().parents[1]


class Assets(unittest.TestCase):
    def fixture(self,folder):
        prefix='LMU-Stintrix-v0.4.0'
        windows=folder/(prefix+'-windows-x64.zip');mac=folder/(prefix+'-macos-arm64.zip');dmg=folder/(prefix+'-macos-arm64.dmg')
        with zipfile.ZipFile(windows,'w') as archive:
            archive.writestr('LMU-Stintrix/VERSION','0.4.0\n')
            archive.writestr('LMU-Stintrix/build-manifest.json',json.dumps(dict(version='0.4.0',platform='windows-x64')))
        with zipfile.ZipFile(mac,'w') as archive:
            archive.writestr('LMU-Stintrix.app/Contents/Info.plist',plistlib.dumps(dict(CFBundleShortVersionString='0.4.0')))
            archive.writestr('LMU-Stintrix.app/Contents/MacOS/LMU-Stintrix',bytes.fromhex('cffaedfe0c000001'))
        dmg.write_bytes(b'synthetic DMG; format is checked by native hdiutil in build job')
        build=dict(version='0.4.0',platform='macos-arm64',files={p.name:dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in (mac,dmg)})
        (folder/'macos-build.json').write_text(json.dumps(build))
        return windows,mac,dmg

    def test_complete_matching_assets_emit_checksums_and_missing_or_tampered_mac_blocks_release(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as work:
            folder=Path(work);windows,mac,dmg=self.fixture(folder)
            checks=verify(folder,'0.4.0');self.assertEqual(set(checks),{p.name for p in (windows,mac,dmg)})
            self.assertEqual(len((folder/'SHA256SUMS.txt').read_text().splitlines()),3)
            dmg.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'checksum'):verify(folder,'0.4.0')
            dmg.unlink()
            with self.assertRaisesRegex(ValueError,'Both platform'):verify(folder,'0.4.0')

    def test_private_or_wrong_version_package_cannot_be_published(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as work:
            folder=Path(work);windows,mac,dmg=self.fixture(folder)
            with zipfile.ZipFile(windows,'a') as archive:archive.writestr('LMU-Stintrix/data/Logs/secret/session.json','{}')
            with self.assertRaisesRegex(ValueError,'Private'):verify(folder,'0.4.0')
            self.fixture(folder)
            with zipfile.ZipFile(windows,'w') as archive:
                archive.writestr('LMU-Stintrix/VERSION','0.3.68')
                archive.writestr('LMU-Stintrix/build-manifest.json',json.dumps(dict(version='0.3.68',platform='windows-x64')))
            with self.assertRaisesRegex(ValueError,'Windows build'):verify(folder,'0.4.0')
