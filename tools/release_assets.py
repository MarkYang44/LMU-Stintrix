"""Verify both delivered platforms before publishing one release and checksums."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import plistlib
import re
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def digest(path):
    value=hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda:source.read(1024*1024),b''):value.update(block)
    return value.hexdigest()


def check_zip(path):
    with zipfile.ZipFile(path) as archive:
        names=archive.namelist()
        if len(names)!=len(set(names)):raise ValueError('Duplicate distribution ZIP members')
        for name in names:
            parts=PurePosixPath(name).parts
            if name.startswith('/') or '\\' in name or '..' in parts:raise ValueError('Unsafe distribution ZIP member')
            if set(p.casefold() for p in parts)&{'data','logs','demologs','importedlogs','recoveredlogs','personalrecords'}:
                raise ValueError('Private data in distribution')
            if parts and parts[-1].casefold() in ('session.json','local_settings.json','_folder_import_receipt.json'):
                raise ValueError('Private settings in distribution')
        if archive.testzip() is not None:raise ValueError('Distribution ZIP CRC mismatch')
        return names


def verify(folder,version):
    if not re.fullmatch(r'\d+\.\d+\.\d+',version):raise ValueError('Invalid version')
    folder=Path(folder);prefix='LMU-Stintrix-v'+version
    files=[folder/(prefix+suffix) for suffix in ('-windows-x64.zip','-macos-arm64.zip','-macos-arm64.dmg')]
    if not all(path.is_file() and not path.is_symlink() and path.stat().st_size>0 for path in files):
        raise ValueError('Both platform packages and the DMG must be present')
    windows,mac,dmg=files
    check_zip(windows);check_zip(mac)
    with zipfile.ZipFile(windows) as archive:
        manifest=json.loads(archive.read('LMU-Stintrix/build-manifest.json'))
        if manifest.get('version')!=version or manifest.get('platform')!='windows-x64':raise ValueError('Wrong Windows build')
        if archive.read('LMU-Stintrix/VERSION').decode().strip()!=version:raise ValueError('Windows version mismatch')
    with zipfile.ZipFile(mac) as archive:
        info=plistlib.loads(archive.read('LMU-Stintrix.app/Contents/Info.plist'))
        if info.get('CFBundleShortVersionString')!=version:raise ValueError('Mac version mismatch')
        with archive.open('LMU-Stintrix.app/Contents/MacOS/LMU-Stintrix') as source:header=source.read(8)
        if header[:4]!=bytes.fromhex('cffaedfe') or int.from_bytes(header[4:8],'little')!=0x100000c:
            raise ValueError('Mac executable must be native arm64')
    build=json.loads((folder/'macos-build.json').read_text('utf-8'))
    if build.get('version')!=version or build.get('platform')!='macos-arm64':raise ValueError('Wrong Mac build manifest')
    checksums={path.name:digest(path) for path in files}
    for path in (mac,dmg):
        metadata=build['files'][path.name]
        if metadata.get('bytes')!=path.stat().st_size or metadata.get('sha256')!=checksums[path.name]:
            raise ValueError('Mac artifact checksum mismatch')
    output=folder/'SHA256SUMS.txt'
    output.write_text(''.join(f'{checksum}  {name}\n' for name,checksum in checksums.items()),encoding='ascii')
    return checksums


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--directory',type=Path,required=True);args=parser.parse_args()
    result=verify(args.directory,(ROOT/'VERSION').read_text().strip())
    print(json.dumps(dict(ok=True,assets=result),indent=2))


if __name__=='__main__':main()
