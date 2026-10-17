"""Capture real bilingual Windows UI with isolated, generated sample sessions.

Run from the configured source environment; outputs remain private until reviewed.
No personal sessions are read and no production widgets or business rules patched.
"""
import argparse
import csv
from datetime import datetime,timedelta,timezone
import json
import math
import os
from pathlib import Path
import sys
import time
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]


def sessions(data):
    from app_config import COLUMNS
    from laps import export_fastest
    for index in range(8):
        spa=index>=4;track='Circuit de Spa-Francorchamps' if spa else 'Fuji Speedway'
        length=7004 if spa else 4535.8;car='Porsche 911 GT3 R LMGT3' if spa else 'BMW M4 LMGT3'
        start=datetime(2026,10,1+index,12,tzinfo=timezone.utc)
        folder=data/'Logs'/f'{start:%Y-%m-%d_%H-%M-%S}_Race_{track}';folder.mkdir(parents=True)
        durations=[round((147 if spa else 103)+(3-lap)*.6-(index%4)*.3,1) for lap in range(4)]
        metadata=dict(track=track,track_layout=track,vehicle=car,vehicle_class='LMGT3',driver='Documentation fixture',
            session=10,started_utc=start.isoformat(),ended_utc=(start+timedelta(seconds=sum(durations))).isoformat(),
            source='Documentation fixture',status='complete',end_reason='finish flag 1',race_mode='single',track_length_m=length)
        (folder/'session.json').write_text(json.dumps(metadata),encoding='utf8')
        with (folder/'inputs.csv').open('w',newline='',encoding='utf8') as stream:
            writer=csv.DictWriter(stream,fieldnames=COLUMNS);writer.writeheader();elapsed=0.
            for lap,duration in enumerate([*durations,.1]):
                for tick in range(round(duration*10)):
                    t=tick/10;phase=t/duration if lap<4 else 0
                    brake=max(0,math.sin(phase*math.tau*4+.8))**10*.8
                    throttle=max(0,min(1,1-brake*1.8-max(0,math.sin(phase*math.tau*4+1.6))*.3))
                    row=dict(time_s=elapsed+t,utc=(start+timedelta(seconds=elapsed+t)).isoformat(),session_time_s=elapsed+t,
                        lap=lap,lap_distance_m=phase*length,throttle=throttle,brake=brake,steering=.5*math.sin(phase*math.tau*3),
                        filtered_throttle=throttle,filtered_brake=brake,filtered_steering=.5*math.sin(phase*math.tau*3),
                        speed_kmh=100+170*throttle-50*brake,lap_start_s=elapsed,lap_invalidated=0,in_pits=0,track_length_m=length,
                        world_x_m=300*math.cos(phase*math.tau),world_y_m=0,world_z_m=180*math.sin(phase*math.tau),
                        fuel_l=55-lap*2-phase*2,tyre_front_name='Medium',tyre_rear_name='Medium',tyre_compound=1,
                        tyre_rear_compound=1,ambient_temp_c=20,track_temp_c=29,wetness=0,rain=0,tc_level=3,abs_level=4)
                    writer.writerow({k:v for k,v in row.items() if k in COLUMNS})
                elapsed+=duration
        export_fastest(folder,ROOT/'src/compare.html')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--work',type=Path);args=parser.parse_args()
    work=(args.work or ROOT/'_local/readme-capture'/datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')).resolve()
    if not work.is_relative_to(ROOT/'_local') or work.exists():raise ValueError('Use a new directory inside this project _local')
    data=work/'fixture-data';data.mkdir(parents=True);out=work/'screenshots'
    os.environ['LMU_STINTRIX_DATA_DIR']=str(data);os.environ['LMU_STINTRIX_REDUCED_MOTION']='1'
    sys.path.insert(0,str(ROOT/'src'))
    from PIL import ImageGrab
    import control_center,i18n
    from control_record_art import RecordHeader
    from control_fields import Select
    from hud import App
    sessions(data);(data/'interface_settings.json').write_text('{"theme":"dark","language":"en"}',encoding='utf8')
    errors=[];evidence=[]
    def descendants(widget):
        for child in widget.winfo_children():yield child;yield from descendants(child)
    def pump(center,condition=lambda:True,seconds=25):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            center.root.update();time.sleep(.01)
            if condition():
                for _ in range(12):center.root.update();time.sleep(.01)
                return
        raise RuntimeError('Actual screenshot UI did not settle')
    def capture(window,path,center):
        window.lift();pump(center);window.update_idletasks()
        # Capture this application's client area only. Never paint or relabel it.
        bitmap=ImageGrab.grab(window=int(window.frame(),16),include_layered_windows=True)
        x=window.winfo_rootx();y=window.winfo_rooty()
        # Window-handle capture includes decorations; the client crop is identical in both locales.
        import ctypes
        from ctypes import wintypes
        rect=wintypes.RECT();user=ctypes.WinDLL('user32',use_last_error=True)
        user.GetWindowRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
        user.GetWindowRect(int(window.frame(),16),ctypes.byref(rect))
        if bitmap.size!=(window.winfo_width(),window.winfo_height()):
            bitmap=bitmap.crop((x-rect.left,y-rect.top,x-rect.left+window.winfo_width(),y-rect.top+window.winfo_height()))
        path.parent.mkdir(parents=True,exist_ok=True);bitmap.save(path,format='WEBP',lossless=True,method=6)
        evidence.append(dict(file=path.relative_to(out).as_posix(),size=list(bitmap.size),bytes=path.stat().st_size))
    with patch.object(control_center.ControlCenter,'repair_windows_entry'):
        center=control_center.ControlCenter();center.root.geometry('1280x900+40+40')
        center.root.report_callback_exception=lambda *args:errors.append(str(args))
        try:
            for language in ('en','zh-CN'):
                target='en' if language=='en' else 'zh'
                if i18n.language!=target:center.toggle_language()
                center.show_page(0);pump(center);capture(center.root,out/language/'control-center.webp',center)
                center.show_page(1);pump(center,lambda:len(center.items)==8)
                # Show the actual library table below its optional filter controls.
                center.scroll.yview_moveto(max(0,center.tree.winfo_rooty()-center.content.winfo_rooty()-35)/max(1,center.content.winfo_height()))
                pump(center);capture(center.root,out/language/'session-library.webp',center)
                center.show_page(6)
                pump(center,lambda:any(isinstance(w,RecordHeader) and w.picture for w in descendants(center.content)))
                header=next(w for w in descendants(center.content) if isinstance(w,RecordHeader))
                center.scroll.yview_moveto(max(0,header.winfo_rooty()-center.content.winfo_rooty()-35)/max(1,center.content.winfo_height()))
                pump(center,lambda:header.picture.photo is not None)
                capture(center.root,out/language/'personal-best.webp',center)
            # The existing clean HUD uses language-neutral traces and pedal bars.
            # One actual DEMO frame is captured in each language; no UI strings are substituted.
            import tkinter as tk
            hud=App(demo=True,clean_controls=True,root=tk.Toplevel(center.root));hud.root.geometry('1280x450+40+40')
            try:
                deadline=time.monotonic()+7
                while time.monotonic()<deadline:pump(center)
                for language in ('en','zh-CN'):
                    i18n.set_language('en' if language=='en' else 'zh')
                    capture(hud.root,out/language/'input-hud.webp',center)
            finally:
                hud.close();pump(center,lambda:not hud.root.winfo_exists())
            assert not errors,errors
        finally:center.close();i18n.set_language('zh')
    result=dict(version=(ROOT/'VERSION').read_text().strip(),data_source='Generated documentation fixtures; input HUD uses built-in DEMO',
        business_logic_changes=False,callback_errors=errors,shots=evidence)
    (work/'capture-evidence.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
