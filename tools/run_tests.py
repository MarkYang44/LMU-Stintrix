"""Run a small change-related scope by default; full regression is explicit."""
import argparse,json,os,subprocess,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.test_scope import SMOKE,changed_paths,related_targets,full_targets


def flatten(suite):
    for case in suite:
        if isinstance(case,unittest.TestSuite):yield from flatten(case)
        else:yield case


def case_names(targets):
    raw=[case.id() for target in targets for case in flatten(unittest.defaultTestLoader.loadTestsFromName(target))]
    names=list(dict.fromkeys(raw));return names,len(raw)-len(names)


def main():
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8',errors='replace')
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--full',action='store_true',help='Explicitly run every historical regression')
    mode.add_argument('--quick',action='store_true',help='Only the six essential smoke checks')
    mode.add_argument('--modules','--tests',dest='targets',nargs='+',help='Exact unittest modules, classes or cases')
    parser.add_argument('--paths',nargs='+',help='Choose related checks for these changed project files')
    parser.add_argument('--base',help='Compare changes to this Git commit or ref (CI/committed work)')
    parser.add_argument('--plan',action='store_true',help='List the selected cases without running them')
    args=parser.parse_args();paths=[]
    try:
        if args.full:targets=full_targets();scope='full (explicit)'
        elif args.quick:targets=list(SMOKE);scope='smoke'
        elif args.targets:targets=args.targets;scope='explicit'
        else:
            if args.paths:paths=args.paths;base=None
            else:paths,base=changed_paths(args.base)
            targets=related_targets(paths,base);scope='related' if paths else 'smoke (no pending changes)'
        names,removed=case_names(targets)
    except (OSError,ValueError,SyntaxError,subprocess.CalledProcessError) as error:
        parser.error(str(error))
    plan=dict(scope=scope,changed_files=paths,selected=len(names),duplicates_removed=removed,tests=names)
    if args.plan:print(json.dumps(plan,ensure_ascii=False,indent=2));return 0
    print(f"Scope: {scope}; {len(names)} selected; {removed} duplicate entries removed",flush=True)
    if not names:print('No runtime checks needed for documentation-only changes.',flush=True);return 0
    failed=[]
    for name in names:
        try:
            result=subprocess.run([sys.executable,'-m','unittest',name,'-q'],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=180,env={**os.environ,'LMU_STINTRIX_HOTKEYS':'0'})
            ok=result.returncode==0;output=result.stdout+result.stderr
        except subprocess.TimeoutExpired:ok=False;output='Selected test exceeded its 180 second limit.'
        print(('PASS' if ok else 'FAIL')+' '+name,flush=True)
        if not ok:failed.append(name);print(output,flush=True)
    print(f'{len(names)-len(failed)}/{len(names)} passed');return int(bool(failed))

if __name__=='__main__':raise SystemExit(main())
