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
    mac=''
    if tuple(map(int,version.split('.'))) >= (0,4,0):
        prefix=f'{base}/releases/download/v{version}/LMU-Stintrix-v{version}'
        mac=(f'**[macOS Apple Silicon · DMG]({prefix}-macos-arm64.dmg)** · '
            f'[macOS .app ZIP]({prefix}-macos-arm64.zip) · '
            f'[SHA256]({base}/releases/download/v{version}/SHA256SUMS.txt)\n\n'
            'Mac：打开 DMG，将 `.app` 拖到 Applications。macOS 13+ / Apple Silicon；'
            '离线分析版，默认临时签名、未公证，首次运行可能需在“隐私与安全”允许。\n\n'
            'Mac: drag the app to Applications. Apple Silicon / macOS 13+; offline analysis. '
            'Ad-hoc signed, not notarized; first launch may need Open Anyway in Privacy & Security. '
            f'[Mac guide]({source}/docs/MACOS.md)\n\n')
    return (
        '## 下载 / Download\n\n'
        f'**[Windows x64 便携版 · v{version}]({asset})**\n\n'+mac+
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
