"""Immutable, metadata-keyed local JS resources, with standalone export."""
import json,os,re,shutil
from pathlib import Path
from cache_tokens import token
PATTERN=re.compile(r'<script type="module" data-stintrix-main>(.*?)</script>',re.S)
SHARED=re.compile(r'<script data-stintrix-main data-stintrix-shared="([0-9a-f]{32})" src="([^"]+)"></script>')


def prepare(path,source,assets,root):
    path,assets,root=Path(path),Path(assets),Path(root)
    if path.parent.parent.name not in ('Logs','DemoLogs','ImportedLogs','RecoveredLogs'):return source
    match=PATTERN.search(source)
    if not match:return source
    from paths import APP_ROOT,track_catalog_path,data_directory
    files=[*assets.glob('*.js'),assets/'report.html',assets/'compare.html',APP_ROOT/'VERSION',track_catalog_path(assets),data_directory()/'interface_settings.json']
    signature=[(str(p),p.stat().st_size,p.stat().st_mtime_ns) for p in files if p.is_file()]
    identity=token(root,'report-resource',[path.name.startswith('fastest') or path.name.endswith('Compare.html'),signature])
    shared=root/'ReportAssets'/identity;shared.mkdir(parents=True,exist_ok=True);resource=shared/'main.js'
    if not resource.is_file():
        pending=resource.with_suffix('.pending');pending.write_text('globalThis.StintrixAssetSources ||= {};\nglobalThis.StintrixAssetSources["'+identity+'"] = async function(){\n'+match[1]+'\n};globalThis.StintrixAssetSources["'+identity+'"]();',encoding='utf8');pending.replace(resource)
    local=path.parent/'.stintrix-assets';local.mkdir(exist_ok=True);link=local/(identity+'.js')
    if not link.is_file():
        try:os.link(resource,link)
        except OSError:shutil.copyfile(resource,link)
    return source[:match.start()]+f'<script data-stintrix-main data-stintrix-shared="{identity}" src=".stintrix-assets/{identity}.js"></script>'+source[match.end():]


def standalone(path):
    path=Path(path);source=path.read_text(encoding='utf8')
    def embed(match):
        resource=(path.parent/match[2]).resolve()
        if not resource.is_relative_to((path.parent/'.stintrix-assets').resolve()):raise ValueError('Invalid report resource path')
        text=resource.read_text(encoding='utf8');body=text.split(' = async function(){\n',1)[1].rsplit('\n};globalThis.StintrixAssetSources',1)[0]
        return '<script type="module" data-stintrix-main>'+body+'</script>'
    return SHARED.sub(embed,source)


def export(path,target):
    target=Path(target);pending=target.with_name(target.name+'.pending')
    try:pending.write_text(standalone(path),encoding='utf8');pending.replace(target)
    finally:pending.unlink(missing_ok=True)
    return str(target)
