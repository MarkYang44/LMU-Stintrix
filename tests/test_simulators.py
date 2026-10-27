"""Focused dual-simulator boundaries, real storage round trip and serial GUI lifecycle."""
import csv
import ctypes
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))


def frame(packet=1):
    from acevo import extract,SPageFilePhysics,SPageFileGraphicEvo,SPageFileStaticEvo
    p=SPageFilePhysics();g=SPageFileGraphicEvo();s=SPageFileStaticEvo()
    p.packetId=packet;p.gas=.123456789;p.brake=.23456789;p.steerAngle=-.3456789;p.speedKmh=180.12345
    g.packetId=packet;g.status=2;g.car_location=4;g.car_model=b'Test Car';g.is_valid_lap=True
    g.gas_percent=.56789123;g.brake_percent=.456789;g.steering_percent=.345678
    g.current_lap_time_ms=12345;g.npos=.12345678
    s.sm_version=b'1.0';s.ac_evo_version=b'fixture';s.track=b'EVO Test';s.track_length_m=4909.;s.session=1
    return p,g,s,extract(p,g,s,123456.123456789+packet)


class Rules(unittest.TestCase):
    def test_windows_maps_are_read_only_fresh_packets_and_pause_safe(self):
        import mmap,uuid
        import acevo
        p,g,s,_=frame();prefix='Stintrix_EVO_Test_'+uuid.uuid4().hex
        pages=[mmap.mmap(-1,ctypes.sizeof(value),tagname=prefix+str(i)) for i,value in enumerate((p,g,s))]
        try:
            for page,value in zip(pages,(p,g,s)):page.write(bytes(value))
            maps=tuple((key,prefix+str(i),kind) for i,(key,_,kind) in enumerate(acevo.MAPS))
            with patch('acevo.MAPS',maps):reader=acevo.SharedReader()
            try:
                self.assertIsNone(reader.read());self.assertIsNone(reader.read())
                p.packetId+=1;p.gas=.987654321;pages[0].seek(0);pages[0].write(bytes(p))
                self.assertEqual(reader.read()['controls'][0],float(p.gas))
                g.status=3;g.packetId+=1;pages[1].seek(0);pages[1].write(bytes(g));self.assertIsNone(reader.read())
                for page,value in zip(pages,(p,g,s)):page.seek(0);self.assertEqual(page.read(),bytes(value))
                self.assertTrue(reader.interface_status()['read_only'])
            finally:reader.close()
        finally:
            for page in pages:page.close()

    def test_wire_sources_and_replay_spectator_invalid_fields(self):
        from acevo import extract,SPageFileGraphicEvo,SPageFileStaticEvo
        p,g,s,value=frame()
        self.assertEqual(SPageFileGraphicEvo.session_state.offset,2476)
        self.assertEqual(SPageFileGraphicEvo.car_ids.offset,3940)
        self.assertEqual(SPageFileStaticEvo.track.offset,136)
        self.assertEqual(value['controls'][0],float(p.gas));self.assertNotEqual(value['controls'][:3],value['controls'][3:])
        self.assertNotIn('lap_start',value);self.assertNotIn('session_clock',value);self.assertNotIn('vehicle_data',value)
        for status in (0,1,3):g.status=status;self.assertIsNone(extract(p,g,s,1))
        g.status=2;g.focused_car_id_a=5;self.assertIsNone(extract(p,g,s,1));g.focused_car_id_a=0
        p.brake=float('nan');self.assertIsNone(extract(p,g,s,1))

    def test_roots_inventory_recent_and_worker_scope_are_separate(self):
        from simulators import root_for,initialize
        from paths import data_directory
        from library import inventory
        from recent_session import checked
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            base=Path(t);(base/'interface_settings.json').write_text('{"language":"en"}')
            (base/'library_notes.json').write_text('{"private":"keep in LMU"}')
            evo=initialize(base,'ac_evo');self.assertEqual(root_for(base,'lmu'),base)
            self.assertTrue((evo/'interface_settings.json').exists());self.assertFalse((evo/'library_notes.json').exists())
            for root,game in ((base,'lmu'),(evo,'ac_evo')):
                for name,tag in (('own',game),('foreign','ac_evo' if game=='lmu' else 'lmu')):
                    folder=root/'Logs'/name;folder.mkdir(parents=True)
                    meta=dict(track='Test',vehicle='Car',driver='Driver',status='complete',session=10,started_utc='2026-01-01')
                    if tag!='lmu':meta['simulator_id']=tag
                    (folder/'session.json').write_text(json.dumps(meta))
                self.assertEqual([v['key'] for v in inventory(root)],['Logs\\own'])
                self.assertIsNone(checked(root,root/'Logs'/'foreign'))
            with patch.dict(os.environ,{'LMU_STINTRIX_DATA_DIR':str(base),'STINTRIX_SIMULATOR':'ac_evo','LMU_STINTRIX_REPORT_WORKER':'0'}):self.assertEqual(data_directory(),evo)
            with patch.dict(os.environ,{'LMU_STINTRIX_DATA_DIR':str(evo),'STINTRIX_SIMULATOR':'lmu','LMU_STINTRIX_REPORT_WORKER':'1'}):self.assertEqual(data_directory(),evo)

    def test_evo_record_lossless_compression_and_archive_reject_cross_game(self):
        from recorder import Recorder
        from session_reports import make_report
        from telemetry_file import Path as TelemetryPath
        from session_archive import export_session,import_session
        from report_state import current
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            base=Path(t);root=base/'Simulators'/'ac_evo';root.mkdir(parents=True)
            (root/'storage_settings.json').write_text('{"auto_compress":true,"columnar":true}')
            gate=threading.Event();errors=[]
            def report(folder):
                gate.wait(10)
                try:
                    with patch('session_compression.ntfs',return_value=False),patch('race_report.generate',return_value={}):make_report(folder)
                except Exception as error:errors.append(error)
            with patch('recorder.Recorder._report',side_effect=report):
                rec=Recorder(root/'Logs');v=frame()[3];rec.start(v)
                for packet in range(1,129):rec.add(frame(packet)[3])
                rec.finish('manual stop')
                original=(rec.folder/'inputs.csv').read_bytes();gate.set()
                for worker in rec.pending_reports:worker.join(15);self.assertFalse(worker.is_alive())
            self.assertFalse(errors);self.assertEqual(current(rec.folder)['state'],'ready')
            self.assertEqual(set(current(rec.folder)['steps']),{'fastest','review','images','compression'})
            self.assertTrue((rec.folder/'inputs.csv.stc').exists())
            self.assertEqual(TelemetryPath(rec.folder/'inputs.csv').read_bytes(),original)
            rows=list(csv.DictReader(io.StringIO(original.decode('utf-8-sig'))))
            self.assertEqual(float(rows[0]['throttle']),v['controls'][0]);self.assertEqual(rows[0]['session_time_s'],'')
            self.assertEqual(rows[0]['lap_start_s'],'');self.assertEqual(rows[0]['world_x_m'],'')
            self.assertNotEqual(rows[0]['throttle'],rows[0]['filtered_throttle'])
            package=export_session(root,str(rec.folder.relative_to(root)),base/'exports')['path']
            target=base/'restored'/'Simulators'/'ac_evo';result=import_session(target,package)
            restored=Path(result['folder']);self.assertEqual(TelemetryPath(restored/'inputs.csv').read_bytes(),original)
            self.assertEqual(json.loads((restored/'session.json').read_text())['simulator_id'],'ac_evo')
            with self.assertRaisesRegex(ValueError,'模拟器'):import_session(base/'lmu-import',package)
            self.assertFalse(list((base/'lmu-import'/'ImportedLogs').glob('*/session.json')))

    def test_failed_game_launch_restores_previous_selection(self):
        from simulators import launch
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            base=Path(t);path=base/'simulator_settings.json';path.write_bytes(b'{"simulator":"lmu"}')
            before=path.read_bytes()
            with patch('subprocess.Popen',side_effect=OSError('fixture unavailable')):
                with self.assertRaises(OSError):launch(base,'ac_evo')
            self.assertEqual(path.read_bytes(),before)


class UI(unittest.TestCase):
    def test_both_modes_pages_hud_and_switch_wait_for_pending_writes(self):
        # Separate, serial Tk processes. No global roots or personal settings are patched in place.
        script=r'''
import sys,time,threading,ctypes,traceback
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8');sys.path.insert(0,str(Path.cwd()/'src'))
ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
from unittest.mock import patch
from control_center import ControlCenter
from app_config import SIMULATOR,ROOT
gate=threading.Event();events=[];errors=[]
def report(folder):gate.wait(15)
with patch.object(ControlCenter,'repair_windows_entry'),patch('recorder.Recorder._report',side_effect=report),patch('control_simulator.launch',side_effect=lambda base,target:events.append(target)):
 app=ControlCenter();app.root.report_callback_exception=lambda *args:errors.append(''.join(traceback.format_exception(*args)))
 def pump(seconds=.12):
  until=time.monotonic()+seconds
  while time.monotonic()<until:
   try:app.root.update()
   except Exception:break
   time.sleep(.005)
 assert app.simulator==SIMULATOR
 for page in (1,3,4,2,0):app.show_page(page);pump()
 app.set_theme('light');pump();app.toggle_language();pump();app.set_theme('dark');pump()
 assert app.simulator_selector.winfo_ismapped()
 assert app.simulator_selector.winfo_rootx()+app.simulator_selector.winfo_width()<=app.shell.language_button.winfo_rootx()
 app.root.update_idletasks()
 from PIL import ImageGrab
 p=Path('_local/acevo');p.mkdir(parents=True,exist_ok=True)
 ImageGrab.grab(bbox=(app.root.winfo_rootx(),app.root.winfo_rooty(),app.root.winfo_rootx()+app.root.winfo_width(),app.root.winfo_rooty()+app.root.winfo_height())).save(p/('preview-'+SIMULATOR+'.png'))
 app.start(True);pump(.3);assert app.hud.engine.recorder.samples>0
 if SIMULATOR=='ac_evo':
  from hud_presentation import visible
  assert not visible(app.hud,'tyres');assert not visible(app.hud,'stint')
 target='ac_evo' if SIMULATOR=='lmu' else 'lmu'
 app.simulator_choice.set(target);app.simulator_selector.event_generate('<<ComboboxSelected>>');pump(.2)
 assert not events,'Switched before save finished';gate.set();pump(.8)
 assert events==[target],events
 assert not errors,errors
 print(SIMULATOR,'GUI and deferred switch OK')
'''
        for game in ('lmu','ac_evo'):
            with self.subTest(game=game),tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
                env=dict(os.environ,LMU_STINTRIX_DATA_DIR=t,STINTRIX_SIMULATOR=game,LMU_STINTRIX_HOTKEYS='0',PYTHONIOENCODING='utf-8')
                child=subprocess.run([sys.executable,'-c',script],cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',timeout=45)
                self.assertEqual(child.returncode,0,child.stdout+child.stderr)


if __name__=='__main__':unittest.main()
