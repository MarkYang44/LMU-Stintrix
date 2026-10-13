"""Select a real LZX-capable CI fixture volume; never bypass compression checks."""
import json,os,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from session_compression import compress

def main():
    if os.name!='nt':raise SystemExit('Native compression fixtures require Windows')
    bases=[Path(os.environ.get('RUNNER_TEMP',str(ROOT/'_local')))]
    if os.environ.get('LOCALAPPDATA'):bases.append(Path(os.environ['LOCALAPPDATA'])/'Temp')
    for base in dict.fromkeys(bases):
        base.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='stintrix-lzx-probe-',dir=base) as t:
            folder=Path(t);(folder/'session.json').write_text('{"status":"complete"}',encoding='utf-8')
            payload=b'time_s,throttle\n'+b'0.123456789012345,0.987654321012345\n'*9000
            sample=folder/'inputs.csv';sample.write_bytes(payload);result=compress(folder)
            assert sample.read_bytes()==payload,'Probe changed original bytes'
            print(json.dumps(dict(volume=base.anchor,supported=result['supported'],saved_bytes=result['saved_bytes'],errors=result['errors'])),flush=True)
            if result['supported'] and not result['errors'] and result['saved_bytes']>0:
                env_file=os.environ.get('GITHUB_ENV')
                if not env_file:raise SystemExit('This helper configures CI fixtures only')
                with Path(env_file).open('a',encoding='utf-8') as stream:stream.write('LMU_STINTRIX_COMPRESSION_TEST_DIR='+str(base.resolve())+'\n')
                print('Native LZX fixture volume confirmed; full compression assertions remain enabled',flush=True);return
            diagnostic=subprocess.run([str(Path(os.environ['SystemRoot'])/'System32/compact.exe'),'/c','/exe:LZX',str(sample)],capture_output=True)
            print(diagnostic.stdout.decode(errors='replace')+diagnostic.stderr.decode(errors='replace'),flush=True)
    raise SystemExit('No LZX-capable fixture volume found; validation must not be skipped')

if __name__=='__main__':main()
