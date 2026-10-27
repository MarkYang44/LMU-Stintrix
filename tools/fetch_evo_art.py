"""Cache the reviewed official EVO catalogue in the selected private EVO root."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path)
    options=parser.parse_args()
    from paths import base_data_directory
    from simulators import root_for
    from evo_art import download
    root=options.root or root_for(base_data_directory(),'ac_evo')
    result=download(root)
    print(json.dumps(result,ensure_ascii=True))
    return bool(result['errors'])

if __name__=='__main__':raise SystemExit(main())
