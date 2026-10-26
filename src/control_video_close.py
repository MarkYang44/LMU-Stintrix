"""Protect calibration and let a hidden wizard finish without losing its callbacks."""
import copy
from pathlib import Path
from tkinter import filedialog
from i18n import tr
INPUT_FIELDS=('video','start','end','sample','track','layout','length','telemetry')


def validate_draft(value):
    """Check only optional draft extensions before mutating the current editor."""
    import math
    if not isinstance(value,dict):raise ValueError('标定草稿格式无效')
    points=value.get('partial_points',[])
    if not isinstance(points,list) or len(points)>3 or any(not isinstance(p,list) or len(p)!=2 or any(isinstance(n,bool) or not isinstance(n,(int,float)) or not math.isfinite(n) for n in p) for p in points):raise ValueError('标定草稿格式无效')
    if value.get('partial_target','throttle') not in ('throttle','brake','anchor','distance_box','timer_box'):raise ValueError('标定草稿格式无效')
    inputs=value.get('draft_inputs',{})
    if not isinstance(inputs,dict) or not isinstance(inputs.get('fields',{}),dict):raise ValueError('标定草稿格式无效')
    if any(not isinstance(text,str) for key,text in inputs.get('fields',{}).items() if key in INPUT_FIELDS):raise ValueError('标定草稿格式无效')
    if any(not isinstance(inputs.get(key,''),str) for key in ('marks','sync')):raise ValueError('标定草稿格式无效')


def snapshot(w):
    size=[w.media['width'],w.media['height']] if w.media else w.calibration_size
    inputs=dict(fields={key:w.fields[key].get() for key in INPUT_FIELDS},mode=w.mode_code(),marks=w.marks.get('1.0','end-1c'),sync=w.sync.get('1.0','end-1c'))
    return dict(geometry=copy.deepcopy(w.geometry),frame_size=size,points=copy.deepcopy(w.clicks),target=w.target.get(),thickness=w.thickness.get(),clockwise={k:v.get() for k,v in w.clockwise.items()},inputs=inputs)


def dirty(w):
    value=snapshot(w);baseline=getattr(w,'saved_calibration',None)
    if baseline is None:return bool(value['geometry'] or value['points'] or value['inputs']['marks'].strip() or value['inputs']['sync'].strip())
    # Changing the current target or preview size alone is not an edit.
    return any(value[key]!=baseline[key] for key in ('geometry','points','thickness','clockwise','inputs'))


def save(w):
    path=filedialog.asksaveasfilename(parent=w.window,title=tr('保存标定草稿'),initialfile='calibration.json',defaultextension='.json',filetypes=[('JSON','*.json')])
    if not path:return False
    value=snapshot(w);geometry=copy.deepcopy(value['geometry'])
    try:
        for key in ('throttle','brake'):
            if key in geometry:geometry[key].update(clockwise=value['clockwise'][key],thickness=float(value['thickness']))
        geometry.update(frame_size=value['frame_size'],partial_points=value['points'],partial_target=value['target'],draft_thickness=value['thickness'],draft_inputs=value['inputs'])
        from storage import atomic_json
        atomic_json(Path(path),geometry);w.saved_calibration=value;w.status.set(tr('标定草稿已保存'));return True
    except (OSError,ValueError) as error:w.status.set(str(error));return False


def allow_exit(w):
    from control_confirm import ask,draft_choice
    if w.busy:
        w.window.deiconify();w.window.lift()
        answer=ask(w.window,'视频任务正在处理','退出程序会取消视频任务。可先处理完当前任务，或请求取消后再退出。',[('stop','请求取消任务'),('cancel','继续处理')])
        if answer=='stop':w.cancel.set();w.status.set(tr('正在取消，保留已有结果…'))
        w.window.deiconify();w.window.lift();return False
    if dirty(w):
        w.window.deiconify();w.window.lift()
        answer=draft_choice(w.window,closing=True,exiting=True,save_label='保存标定并关闭')
        if answer=='cancel' or (answer=='save' and not save(w)):return False
    return True


def restore_inputs(w,value):
    inputs=value.get('draft_inputs')
    if not isinstance(inputs,dict):return
    for key,text in inputs.get('fields',{}).items():
        if key in INPUT_FIELDS:w.fields[key].set(str(text))
    from control_video import MODES
    mode=next((label for label,code in MODES.items() if code==inputs.get('mode')),None)
    if mode:w.mode.set(mode);w.mode_changed()
    for key in ('marks','sync'):
        if key in inputs:
            widget=getattr(w,key);widget.delete('1.0','end');widget.insert('1.0',str(inputs[key]))


def close(w):
    from control_confirm import ask,draft_choice
    if w.busy:
        answer=ask(w.window,'视频任务正在处理','可隐藏窗口继续处理，或取消任务并在完成清理后关闭。',[('background','后台继续处理'),('stop','取消任务并关闭'),('cancel','返回窗口')])
        if answer=='background':w.window.withdraw();w.app.status.set(tr('视频任务在后台处理；可从视频分析入口重新打开'))
        elif answer=='stop':w.close_after_task=True;w.cancel.set();w.status.set(tr('正在取消，保留已有结果…'))
        return
    if dirty(w):
        answer=draft_choice(w.window,closing=True,save_label='保存标定并关闭')
        if answer=='cancel' or (answer=='save' and not save(w)):return
        if answer=='keep':w.window.withdraw();return
    w.cancel.set();w.window.destroy()
