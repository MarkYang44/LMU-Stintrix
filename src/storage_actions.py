"""Explicit CSV / standalone HTML exports and selected-session column storage."""
import shutil
from pathlib import Path
from uuid import uuid4


def columnar(folder):
    from session_compression import compress
    return compress(folder,columnar=True)


def restore(folder):
    from column_store import restore as restore_csv
    from reporting import serialized
    @serialized
    def action():
        import json
        if (Path(folder)/'.storage_compression.pending').exists():raise ValueError('该赛事正在压缩，请稍后恢复 CSV')
        metadata=json.loads((Path(folder)/'session.json').read_text(encoding='utf8'))
        if metadata.get('status')=='recording':raise ValueError('请先停止记录')
        return dict(files=[restore_csv(Path(folder)/name) for name in ('inputs.csv','vehicle.csv')])
    return action()


def export(folder,destination,kind):
    from telemetry_file import Path as ReadPath
    folder=ReadPath(folder).resolve();destination=Path(destination).resolve()
    if destination.is_relative_to(folder):raise ValueError('导出目录不能位于原赛事内部')
    destination.mkdir(parents=True,exist_ok=True)
    if kind=='html':
        from report_assets import export as standalone
        source=folder/'review.html'
        if not source.is_file():raise ValueError('此赛事尚无复盘页')
        target=destination/(folder.name+'-review-'+uuid4().hex[:8]+'.html')
        return dict(path=standalone(source,target))
    target=destination/(folder.name+'-CSV-'+uuid4().hex[:8]);target.mkdir()
    for name in ('inputs.csv','vehicle.csv'):
        source=folder/name
        if source.is_file():
            with source.open('rb') as src,(target/name).open('xb') as out:shutil.copyfileobj(src,out,1048576)
    return dict(path=str(target))
