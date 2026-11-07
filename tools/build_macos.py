"""Native Apple Silicon offline .app, ZIP and DMG; no private data or EXEs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import plistlib
import shutil
import subprocess
import sys
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.build import ASSET_NAMES


def run(*args,**kwargs):return subprocess.run(list(map(str,args)),check=True,**kwargs)


def audit_app(app):
    from tools.audit_publication import PRIVATE_NAMES,PRIVATE_PARTS
    for path in app.rglob('*'):
        rel=path.relative_to(app)
        if path.is_symlink():
            if not path.resolve().is_relative_to(app.resolve()):raise ValueError('External bundle link: '+str(rel))
            continue
        if not path.is_file():continue
        if (set(p.casefold() for p in rel.parts)&PRIVATE_PARTS or path.name.casefold() in PRIVATE_NAMES
                or path.name=='_folder_import_receipt.json' or path.suffix.casefold() in ('.exe','.dll','.pyd','.csv','.duckdb','.stc','.log')):
            raise ValueError('Private or Windows-only file in macOS bundle: '+str(rel))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--skip-dmg',action='store_true');args=parser.parse_args()
    if sys.platform!='darwin' or platform.machine()!='arm64' or sys.version_info[:2]!=(3,13):
        raise SystemExit('Build on Apple Silicon macOS with arm64 CPython 3.13 (not Rosetta).')
    run(sys.executable,ROOT/'tools/audit_publication.py','--working-tree',cwd=ROOT)
    version=(ROOT/'VERSION').read_text().strip();work=ROOT/'_local/macos-build'/uuid4().hex[:12];work.mkdir(parents=True)
    stage=work/'dist';dist=ROOT/'dist';dist.mkdir(exist_ok=True)
    from tools.build_brand import render
    from tools.install_macos_7zip import install
    brand=render(work/'branding');console=install()
    from PIL import Image
    with Image.open(ROOT/'src/branding/stx-app.png') as image:image.save(brand/'stintrix.icns',format='ICNS')
    helper=ROOT/'_local/macos-tools/vision-ocr';helper.parent.mkdir(parents=True,exist_ok=True)
    run('xcrun','swiftc','-O','-target','arm64-apple-macos13.0',ROOT/'tools/macos_ocr.swift',
        '-framework','Vision','-framework','Foundation','-framework','ImageIO','-o',helper)
    asset=work/'build-version.json';asset.write_text(json.dumps(dict(version=version,platform='macos-arm64',offline=True)))
    command=[sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onedir','--windowed','--noupx',
        '--name','LMU-Stintrix','--paths',str(ROOT/'src'),'--target-arch','arm64',
        '--osx-bundle-identifier','io.github.MarkYang44.LMU-Stintrix','--icon',str(brand/'stintrix.icns'),
        '--workpath',str(work/'work'),'--specpath',str(work),'--distpath',str(stage),'--collect-all','duckdb']
    # macOS never imports/loads live adapters, Win32 integration or the external
    # Windows renderer. The Windows build and its hidden imports are unchanged.
    for name in ('hud','engine','recorder','telemetry','acevo','native_hotkeys','windows_integration','windows_png',
        'telemetry_contract','pyLMUSharedMemory','racecom_bridge','doctor','release_smoke','tests','tools'):
        command+=['--exclude-module',name]
    command+=['--add-data',str(asset)+':src','--add-binary',str(console)+':src/tools','--add-binary',str(helper)+':src/tools']
    for name in ASSET_NAMES:
        if name=='racecom_validity_hook.py':continue
        file=ROOT/'src'/name;command+=['--add-data',str(file)+':'+(Path('src')/Path(name).parent).as_posix()]
    for file in brand.iterdir():
        if file.suffix in ('.png','.ico'):command+=['--add-data',str(file)+':src/branding']
    for file in (ROOT/'src/guide/media').rglob('*.webp'):
        command+=['--add-data',str(file)+':'+file.parent.relative_to(ROOT).as_posix()]
    command.append(str(ROOT/'src/inputscope.py'))
    run(*command,cwd=ROOT,env={**os.environ,'MACOSX_DEPLOYMENT_TARGET':'13.0'})
    app=stage/'LMU-Stintrix.app';resources=app/'Contents/Resources'
    docs=resources/'docs';docs.mkdir(exist_ok=True)
    for name in ('MACOS.md','PRIVACY.md','DATA_PROCESSING.md','SIMULATORS.md','STORAGE_OPTIMIZATION.md'):
        shutil.copy2(ROOT/'docs'/name,docs/name)
    for name in ('LICENSE','THIRD_PARTY_NOTICES.md'):shutil.copy2(ROOT/name,resources/name)
    licenses=resources/'licenses';licenses.mkdir(exist_ok=True)
    shutil.copy2(console.with_name('License.txt'),licenses/'7zip-License.txt')
    for name in ('pillow','duckdb','resvg_py','pyinstaller','macholib','altgraph'):
        import importlib.metadata as metadata
        distribution=metadata.distribution(name)
        for item in distribution.files or ():
            if any(word in item.name.casefold() for word in ('license','copying','notice')) and item.suffix.casefold() in ('','.txt','.md'):
                file=Path(distribution.locate_file(item))
                if file.is_file():shutil.copy2(file,licenses/(name+'-'+file.name))
    info=app/'Contents/Info.plist'
    with info.open('rb') as stream:value=plistlib.load(stream)
    value.update(CFBundleShortVersionString=version,CFBundleVersion=version,LSMinimumSystemVersion='13.0',
        NSHighResolutionCapable=True,CFBundleDisplayName='Stintrix · Offline Analysis',
        NSHumanReadableCopyright='LMU-Stintrix contributors')
    with info.open('wb') as stream:plistlib.dump(value,stream)
    audit_app(app)
    # Ad-hoc signing is sufficient for local builds, and needs no private key.
    # A Developer ID installed in the runner keychain may be selected for release.
    identity=os.environ.get('STINTRIX_MAC_SIGN_IDENTITY','-')
    run('codesign','--force','--deep','--sign',identity,app)
    run('codesign','--verify','--deep','--strict','--verbose=2',app)
    archive=dist/f'LMU-Stintrix-v{version}-macos-arm64.zip'
    run('ditto','-c','-k','--sequesterRsrc','--keepParent',app,archive)
    if not args.skip_dmg:
        dmgroot=work/'dmg';dmgroot.mkdir();run('ditto',app,dmgroot/app.name)
        (dmgroot/'Applications').symlink_to('/Applications',target_is_directory=True)
        shutil.copy2(ROOT/'docs/MACOS.md',dmgroot/'Read Me.md')
        run('hdiutil','create','-volname','Stintrix Offline','-srcfolder',dmgroot,'-ov','-format','UDZO',
            dist/f'LMU-Stintrix-v{version}-macos-arm64.dmg')
    outputs=[archive]+([] if args.skip_dmg else [dist/f'LMU-Stintrix-v{version}-macos-arm64.dmg'])
    result=dict(version=version,platform='macos-arm64',app=str(app),signed='ad-hoc' if identity=='-' else 'Developer ID',notarized=False,files={})
    for file in outputs:
        digest=hashlib.sha256(file.read_bytes()).hexdigest();result['files'][file.name]=dict(bytes=file.stat().st_size,sha256=digest)
        file.with_suffix(file.suffix+'.sha256').write_text(digest+'  '+file.name+'\n')
    (dist/'macos-build.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
