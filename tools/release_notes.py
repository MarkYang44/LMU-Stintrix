"""Put the portable download first and include only this version's notes."""
import argparse
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
REPOSITORY='MarkYang44/LMU-Stintrix'


def render(version,history):
    if not re.fullmatch(r'\d+\.\d+\.\d+',version):raise ValueError('Invalid release version')
    headings=list(re.finditer(r'^## v(\d+\.\d+\.\d+)(?=\s|$)[^\r\n]*',history,re.MULTILINE))
    selected=next((i for i,heading in enumerate(headings) if heading[1]==version),None)
    if selected is None:raise ValueError('No release notes for v'+version)
    start=headings[selected].start();end=headings[selected+1].start() if selected+1<len(headings) else len(history)
    current=history[start:end].strip()
    base=f'https://github.com/{REPOSITORY}'
    asset=f'{base}/releases/download/v{version}/LMU-Stintrix-v{version}-windows-x64.zip'
    source=f'{base}/blob/v{version}'
    return (
        '## 下载 / Download\n\n'
        f'**[Windows x64 便携版 · v{version}]({asset})**\n\n'
        '完整解压 ZIP，双击 `LMU-Stintrix.exe`；保留同目录的 `_internal`。'
        '升级时保留自己的 `data/` 和 `local_settings.json`。\n\n'
        'Extract the complete ZIP and run `LMU-Stintrix.exe`. '
        'Keep `_internal` beside the EXE; preserve your `data/` and `local_settings.json` when updating.\n\n'
        f'{current}\n\n'
        f'[完整更新历史 / Full changelog]({source}/docs/RELEASE_NOTES.md) · '
        f'[English guide]({source}/README.md) · [中文说明]({source}/README.zh-CN.md)\n'
    )


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    version=(ROOT/'VERSION').read_text('utf-8-sig').strip()
    body=render(version,(ROOT/'docs/RELEASE_NOTES.md').read_text('utf-8-sig'))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(body,'utf-8')
    print(f'Release v{version}: download first, current notes only ({len(body)} characters)')


if __name__=='__main__':main()
