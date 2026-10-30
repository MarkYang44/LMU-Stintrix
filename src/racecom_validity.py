"""Install the small local presentation adapter, preserving prior hook bytes."""
import hashlib
from pathlib import Path
from paths import ASSETS

MARK='# STINTRIX_GAME_VALIDITY_V1'
SUFFIX='''
# STINTRIX_GAME_VALIDITY_V1
_stintrix_prior_install_image = install_image
def install_image(ns):
    _stintrix_prior_install_image(ns)
    import runpy
    runpy.run_path(os.path.join(ROOT, '_customization', 'stintrix_game_validity_v1.py'))['install'](ns)
'''


def prepare(executable):
    base=Path(executable).resolve().parent;hooks=base/'_customization/racecom_hooks.py'
    original=hooks.read_bytes();text=original.decode('utf-8-sig')
    if 'def install_image(' not in text:raise ValueError('图像生成器缺少 install_image 扩展接口；原文件已保留')
    helper=hooks.with_name('stintrix_game_validity_v1.py');wanted=(ASSETS/'racecom_validity_hook.py').read_bytes()
    changes=[]
    if not helper.exists() or helper.read_bytes()!=wanted:changes.append((helper,wanted))
    if MARK not in text:changes.append((hooks,original+SUFFIX.encode('utf-8')))
    if not changes:return
    backup=base/'_stintrix_validity_history'
    for path,content in changes:
        if path.exists():
            prior=path.read_bytes();target=backup/(path.name+'.'+hashlib.sha256(prior).hexdigest()[:16])
            backup.mkdir(exist_ok=True)
            if not target.exists():target.write_bytes(prior)
        pending=path.with_name(path.name+'.validity.pending')
        try:pending.write_bytes(content);pending.replace(path)
        finally:pending.unlink(missing_ok=True)
