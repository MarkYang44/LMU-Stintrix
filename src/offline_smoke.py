"""Opt-in packaged-app smoke probe, using disposable synthetic records only."""
import csv
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time


def fixture(folder,simulator='lmu'):
    folder=Path(folder);folder.mkdir(parents=True)
    meta=dict(status='complete',source='Offline compatibility fixture',session=10,
        simulator_id=simulator,track='Compatibility Circuit',track_layout='GP',track_length=1000,
        vehicle='Compatibility GT3',vehicle_class='GT3',driver='Synthetic driver',
        started_utc='2026-01-01T00:00:00+00:00',ended_utc='2026-01-01T00:01:00+00:00')
    (folder/'session.json').write_text(json.dumps(meta),'utf-8')
    fields=['time_s','utc','session_time_s','lap','lap_distance_m','throttle','brake','steering',
        'filtered_throttle','filtered_brake','filtered_steering','speed_kmh','lap_start_s',
        'lap_invalidated','in_pits','track_length_m','world_x_m','world_y_m','world_z_m']
    if simulator=='ac_evo':fields+=['evo_lap_time_ms','evo_last_lap_time_ms','evo_is_valid_lap','evo_timing_invalid']
    with (folder/'inputs.csv').open('w',newline='',encoding='utf-8') as out:
        writer=csv.DictWriter(out,fieldnames=fields);writer.writeheader()
        for lap in range(4):
            for step in range(100):
                t=lap*10+step/10
                row=dict(time_s=t,utc='2026-01-01T00:00:00Z',session_time_s=t,lap=lap+(simulator=='ac_evo'),
                    lap_distance_m=step*10,throttle='0.12345678901234567',brake=0,steering='-0.01234567890123456',
                    filtered_throttle='.12345678901234567',filtered_brake=0,filtered_steering=0,
                    speed_kmh=150,lap_start_s=lap*10,lap_invalidated=0,in_pits=0,track_length_m=1000,
                    world_x_m=step,world_y_m=0,world_z_m=step)
                if simulator=='ac_evo':row.update(evo_lap_time_ms=step*100,evo_last_lap_time_ms=10000 if lap else 0,evo_is_valid_lap=1,evo_timing_invalid=0)
                writer.writerow(row)
    return folder


def run():
    from app_config import ROOT,SIMULATOR
    from platform_runtime import offline_only,page_ids
    if not offline_only():raise ValueError('Smoke probe requires offline mode')
    with tempfile.TemporaryDirectory(prefix='stintrix-smoke-',dir=ROOT) as work:
        from simulators import root_for
        base=Path(work);folder=fixture(base/'windows'/'session',SIMULATOR);library=root_for(base/'library',SIMULATOR)
        original={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir()}
        from session_import import import_folder
        imported=Path(import_folder(library,folder)['folder'])
        from laps import export_fastest
        from paths import ASSETS
        if SIMULATOR=='ac_evo':
            from evo_laps import export
            export(imported);lap=json.loads((imported/'fastest_lap.json').read_text())
        else:lap,_=export_fastest(imported,ASSETS/'compare.html')
        assert lap['lap']['time_s']==10
        from laps import write_compare
        write_compare(base/'compare.html',ASSETS/'compare.html',[lap,lap])
        assert (base/'compare.html').is_file()
        from personal_records import records
        assert len(records(library))==1
        # Exported curve records can own disk-backed scratch tables. Finish
        # consuming them before enumerating the entire session for archiving.
        del lap
        import gc
        gc.collect()
        from race_report import generate
        receipt=generate(imported,renderer='native')
        assert receipt['status']=='complete'
        from renderer_config import save as save_renderer
        save_renderer(dict(mode='native',executable=''),ROOT)
        from session_reports import make_report
        report=make_report(imported,isolated=True)
        assert report['state']=='ready',report
        assert (imported/'review.html').is_file()
        from PIL import Image
        for name in ('圈速单.png','比赛日志.png'):
            with Image.open(imported/name) as image:image.verify()
        from session_archive import export_session,import_session
        for format in ('zip','7z'):
            package=export_session(library,str(imported.relative_to(library)),base/'exports',format=format)
            result=import_session(root_for(base/format,SIMULATOR),package['path'])
            for name,digest in original.items():assert hashlib.sha256((Path(result['folder'])/name).read_bytes()).hexdigest()==digest
        from control_center import ControlCenter
        app=ControlCenter();errors=[]
        app.root.report_callback_exception=lambda *args:errors.append(str(args[1]))
        for page in page_ids():
            app.show_page(page)
            deadline=time.monotonic()+15
            while not app.pages.active.complete and time.monotonic()<deadline:
                app.root.update();time.sleep(.01)
            assert app.pages.active.complete and not app.pages.active.failed,(page,errors)
        from control_palette import commands
        assert not {'start','demo','layouts','shortcuts','interface'}.intersection(c.key for c in commands(app))
        assert not app.active()
        app.close()
        assert not errors,errors
        if sys.platform=='darwin':
            from video_ocr import create
            from pillow_png import font
            from PIL import ImageDraw
            with Image.new('RGB',(300,100),'white') as sample:
                ImageDraw.Draw(sample).text((20,10),'12345',font=font(50),fill='black')
                ocr=create()
                try:assert '12345' in ''.join(ocr.recognize([sample],base)).replace(' ','')
                finally:ocr.close()
        for name,digest in original.items():assert hashlib.sha256((folder/name).read_bytes()).hexdigest()==digest
    result=dict(ok=True,platform=sys.platform,offline=True,pages=list(page_ids()),imports=['folder','zip','7z'],native_png=True)
    if os.environ.get('STINTRIX_SMOKE_RESULT'):
        Path(os.environ['STINTRIX_SMOKE_RESULT']).write_text(json.dumps(result),'utf-8')
    if sys.stdout is not None:print(json.dumps(result))

