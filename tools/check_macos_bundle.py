"""Verify the delivered ZIP outside the checkout, using only its frozen app."""
import hashlib
import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.build_macos import audit_app


def hashes(app):
    return {str(p.relative_to(app)):hashlib.sha256(p.read_bytes()).hexdigest() for p in app.rglob('*') if p.is_file() and not p.is_symlink()}


def main():
    if sys.platform!='darwin':raise SystemExit('Run the delivered-app check on macOS.')
    version=(ROOT/'VERSION').read_text().strip();dist=ROOT/'dist'
    archive=dist/f'LMU-Stintrix-v{version}-macos-arm64.zip'
    with tempfile.TemporaryDirectory(prefix='Stintrix native verification ') as work:
        base=Path(work);subprocess.run(['ditto','-x','-k',str(archive),str(base)],check=True)
        app=base/'LMU-Stintrix.app';audit_app(app);before=hashes(app)
        with (app/'Contents/Info.plist').open('rb') as source:info=plistlib.load(source)
        assert info['CFBundleShortVersionString']==version
        binary=app/'Contents/MacOS/LMU-Stintrix'
        arch=subprocess.check_output(['lipo','-archs',str(binary)],text=True).strip();assert arch=='arm64',arch
        subprocess.run(['codesign','--verify','--deep','--strict',str(app)],check=True)
        environment={k:v for k,v in os.environ.items() if k not in ('PYTHONPATH','PYTHONHOME','LMU_STINTRIX_REPORT_WORKER')}
        for simulator in ('lmu','ac_evo'):
            data=base/('private data '+simulator);receipt=base/(simulator+'-smoke.json')
            environment.update(LMU_STINTRIX_DATA_DIR=str(data),STINTRIX_SIMULATOR=simulator,
                STINTRIX_OFFLINE='1',STINTRIX_SMOKE_RESULT=str(receipt))
            result=subprocess.run([str(binary),'--offline-smoke'],env=environment,cwd=base,capture_output=True,text=True,timeout=180)
            if result.returncode or not receipt.is_file():
                failures=[str(p)+': '+p.read_text(errors='replace') for p in data.rglob('startup_error.log')]
                raise RuntimeError(str(result.returncode)+' '+result.stderr+' '+str(failures))
            value=json.loads(receipt.read_text());assert value['ok'] and value['native_png'];assert value['platform']=='darwin'
        assert before==hashes(app),'The app wrote into its signed bundle'
    dmg=dist/f'LMU-Stintrix-v{version}-macos-arm64.dmg'
    if dmg.exists():subprocess.run(['hdiutil','verify',str(dmg)],check=True)
    print('Delivered arm64 .app: native launch, both games, ZIP/7z/folder imports, PNG reports and all offline pages PASS')


if __name__=='__main__':main()
