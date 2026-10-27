"""Private renderer preferences; third-party software is never bundled."""
from pathlib import Path
from paths import data_directory
from race_model import read_json
from storage import atomic_json


def load(root=None):
    root=Path(root or data_directory())
    value=read_json(root/'renderer_settings.json',{})
    if not (root/'renderer_settings.json').exists() and root.name=='ac_evo' and root.parent.name=='Simulators':
        # Share the installed engine selection, with independent EVO resources.
        shared=load(root.parent.parent)
        value=shared
    if not isinstance(value,dict):value={}
    mode=value.get('mode','racecom');mode=mode if mode in ('racecom','native') else 'racecom'
    executable=value.get('executable','');executable=executable if isinstance(executable,str) else ''
    if executable and not Path(executable).is_absolute():executable=str((root/executable).resolve())
    return dict(mode=mode,executable=executable)


def save(value,root=None):
    if value.get('mode') not in ('racecom','native'):raise ValueError('请选择图像生成方式')
    executable=str(value.get('executable','')).strip()
    if value['mode']=='racecom' and (not Path(executable).is_file() or Path(executable).name.casefold()!='image generate.exe'):
        raise ValueError('请选择 RaceCom 安装目录里的 Image Generate.exe')
    if value['mode']=='racecom' and not (Path(executable).parent/'Source'/'LMU Logo.png').is_file():
        raise ValueError('生成器旁缺少 Source / LMU Logo.png；请选择完整的 RaceCom 安装目录')
    root=Path(root or data_directory()).resolve()
    if executable and Path(executable).resolve().is_relative_to(root):executable=str(Path(executable).resolve().relative_to(root))
    from preference_error import read_object
    path=root/'renderer_settings.json';saved=read_object(path);saved.update(mode=value['mode'],executable=executable);atomic_json(path,saved)


def resolve(mode=None):
    value=load()
    if mode:
        if mode not in ('racecom','native'):raise ValueError('请选择原版或兼容图像生成方式')
        value['mode']=mode
    if value['mode']=='racecom' and not Path(value['executable']).is_file():
        raise ValueError('尚未配置 RaceCom 原版图像生成器。请在控制中心 → 图像与数据选择 Image Generate.exe；赛事数据已保留。')
    root=Path(data_directory())
    if value['mode']=='racecom' and root.name=='ac_evo' and root.parent.name=='Simulators':
        from evo_art import prepare_renderer
        value['executable']=str(prepare_renderer(root,value['executable']))
    return value
