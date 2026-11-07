"""Install a pinned official universal macOS 7zz into the private build cache."""
import hashlib
import io
from pathlib import Path
import sys
import tarfile
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from sevenzip import VERSION,MAC_SHA256
URL='https://github.com/ip7z/7zip/releases/download/26.04/7z2604-mac.tar.xz'
SHA256='bee04358cbcbc7106273cee0e8d72916db2696c48067a3538c34d8cd6fd16578'


def install():
    target=ROOT/'_local/dependencies/7zip'/VERSION/'7zz';target.parent.mkdir(parents=True,exist_ok=True)
    license=target.with_name('License.txt')
    if target.is_file() and license.is_file() and hashlib.sha256(target.read_bytes()).hexdigest()==MAC_SHA256:
        target.chmod(0o755);return target
    request=urllib.request.Request(URL,headers={'User-Agent':'Stintrix-macOS-build'})
    with urllib.request.urlopen(request,timeout=60) as response:blob=response.read(16*1024**2+1)
    if hashlib.sha256(blob).hexdigest()!=SHA256:raise ValueError('Official macOS 7z archive checksum mismatch')
    with tarfile.open(fileobj=io.BytesIO(blob),mode='r:xz') as archive:
        # Only two known regular members, never extract archive-supplied paths.
        for name,destination in (('7zz',target),('License.txt',license)):
            member=archive.getmember(name)
            if not member.isfile() or member.size>8*1024**2:raise ValueError('Invalid 7z distribution')
            data=archive.extractfile(member).read()
            if name=='7zz' and hashlib.sha256(data).hexdigest()!=MAC_SHA256:raise ValueError('Official 7zz checksum mismatch')
            pending=destination.with_suffix('.pending');pending.write_bytes(data);pending.replace(destination)
    target.chmod(0o755);return target


if __name__=='__main__':print(install())
