"""Hide source fragments only while a complete, provenance-linked merge exists."""
from telemetry_file import Path
from race_model import read_json


def folders(root):
    """One request's canonical event directories; no raw reads or retained cache."""
    root=Path(root).resolve();hidden=superseded(root)
    for category in ('Logs','ImportedLogs','RecoveredLogs','DemoLogs'):
        for path in (root/category).glob('*/session.json'):
            folder=path.parent.resolve()
            if folder not in hidden and folder.is_relative_to(root):yield category,folder


def superseded(root):
    root=Path(root).resolve();value=read_json(root/'SessionGroups/index.json',{});out=set()
    if not isinstance(value,dict):return out
    links=value.get('links',{})
    if not isinstance(links,dict) or len(links)>4096:return out
    for original,merged in links.items():
        source=(root/str(original)).resolve();target=(root/str(merged)).resolve()
        if not source.is_relative_to(root) or not target.is_relative_to(root) or source==target:continue
        if len(source.relative_to(root).parts)!=2 or len(target.relative_to(root).parts)!=2:continue
        m=read_json(target/'session.json',{})
        if not isinstance(m,dict) or m.get('status')!='complete':continue
        if str(source) in m.get('recovery_sources',[]) and (target/'inputs.csv').is_file():out.add(source)
    return out
