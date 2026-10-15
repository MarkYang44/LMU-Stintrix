"""Fetch one pinned, public-domain official console binary; no system install."""
import hashlib,sys,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from sevenzip import VERSION,URL,SHA256

def install(no_checksums=False):
    target=ROOT/'_local/dependencies/7zip'/VERSION/'7zr.exe';target.parent.mkdir(parents=True,exist_ok=True)
    if target.is_file() and (no_checksums or hashlib.sha256(target.read_bytes()).hexdigest()==SHA256):return target
    request=urllib.request.Request(URL,headers={'User-Agent':'LMU-Stintrix-Setup'})
    with urllib.request.urlopen(request,timeout=60) as response:blob=response.read(8*1024**2)
    if not no_checksums and hashlib.sha256(blob).hexdigest()!=SHA256:raise ValueError('Official 7zr SHA256 mismatch')
    pending=target.with_suffix('.pending');pending.write_bytes(blob);pending.replace(target)
    return target

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--no-checksums',action='store_true');args=parser.parse_args()
    target=install(no_checksums=args.no_checksums)
    print('Official 7zr '+VERSION+(': ready; ' if args.no_checksums else ': SHA256 verified; ')+str(target))
