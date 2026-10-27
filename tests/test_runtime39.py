"""Runtime draw/collection separation, EVO snapshots and deferred worker safety."""
import ctypes,json,mmap,os,sys,tempfile,threading,time,unittest,uuid
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))


class Runtime(unittest.TestCase):
    def test_only_evo_engines_hold_the_runtime_gate(self):
        import engine,runtime_activity
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            for game in ('lmu','ac_evo'):
                gate=threading.Event()
                with patch('engine.ROOT',Path(t)),patch('engine.SIMULATOR',game),patch.object(engine.Engine,'run',lambda self:gate.wait(3)):
                    instance=engine.Engine(output=Path(t)/'Logs')
                    try:self.assertEqual(runtime_activity.busy(),game=='ac_evo')
                    finally:instance.stop.set();gate.set();instance.thread.join(4)
                self.assertFalse(runtime_activity.busy())

    def test_duplicate_evo_frames_skip_decoding_but_finish_static_and_raw_fields_are_preserved(self):
        import acevo
        from tests.test_simulators import frame
        p,g,s,_=frame();prefix='Stintrix_Perf_Test_'+uuid.uuid4().hex
        pages=[mmap.mmap(-1,ctypes.sizeof(v),tagname=prefix+str(i)) for i,v in enumerate((p,g,s))]
        def write(i,value):pages[i].seek(0);pages[i].write(bytes(value))
        try:
            for i,value in enumerate((p,g,s)):write(i,value)
            with patch('acevo.MAPS',tuple((k,prefix+str(i),kind) for i,(k,_,kind) in enumerate(acevo.MAPS))):reader=acevo.SharedReader()
            try:
                self.assertIsNone(reader.read());p.packetId+=1;write(0,p);sample=reader.read();self.assertEqual(sample,acevo.extract(p,g,s,sample['et']))
                with patch.object(reader,'snapshot',side_effect=AssertionError('Unchanged pages need no full decode')):
                    for _ in range(40):self.assertIsNone(reader.read())
                s.session_id+=1;write(2,s);self.assertIsNone(reader.read());p.packetId+=1;write(0,p);sample=reader.read();self.assertEqual(sample['session_uid'][1],s.session_id)
                g.packetId+=1;g.session_state.end_session_flag=True;write(1,g);self.assertEqual(reader.read()['finish'],1)
                g.status=3;g.packetId+=1;p.packetId+=1;write(0,p);write(1,g);self.assertIsNone(reader.read())
                for page,value in zip(pages,(p,g,s)):page.seek(0);self.assertEqual(page.read(),bytes(value))
            finally:reader.close()
        finally:
            for page in pages:page.close()

    def test_live_capture_defers_evo_processing_then_dispatches_isolated_worker_without_rewriting_csv(self):
        import runtime_activity,session_reports,report_worker
        from recorder import Recorder
        from report_state import save,current
        class Engine:pass
        engine=Engine();engine.stop=threading.Event();engine.thread=threading.current_thread();runtime_activity.register(engine)
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            root=Path(t)/'Simulators/ac_evo';folder=root/'Logs/test';folder.mkdir(parents=True);(folder/'session.json').write_text('{"status":"complete","simulator_id":"ac_evo"}');(folder/'inputs.csv').write_bytes(b'original CSV evidence')
            try:
                self.assertTrue(runtime_activity.busy())
                with patch('session_reports.ROOT',root),patch('report_worker.subprocess.run') as spawn:
                    Recorder._report(folder);spawn.assert_not_called();self.assertEqual(report_worker.resume_pending(root),0)
                self.assertEqual(json.loads((folder/'report_pending.json').read_text('utf-8'))['status'],'waiting_for_capture');self.assertEqual(current(folder)['state'],'deferred')
                engine.stop.set();self.assertFalse(runtime_activity.busy())
                def completed(path,data_root):
                    self.assertEqual(Path(data_root),root);save(path,{k:dict(state='ready') for k in ('review','compression')});return current(path)
                with patch('session_reports.ROOT',root),patch('report_worker.can_report',return_value=True),patch('report_worker.run',side_effect=completed) as run:
                    self.assertEqual(report_worker.resume_pending(root),1);run.assert_called_once_with(folder,root)
                self.assertFalse((folder/'report_pending.json').exists());self.assertEqual((folder/'inputs.csv').read_bytes(),b'original CSV evidence')
            finally:engine.stop.set()

    def test_new_evo_display_defaults_preserve_sampling_custom_keys_and_existing_preferences(self):
        from simulators import initialize
        from sampling import DEFAULTS
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            root=Path(t);source=dict(DEFAULTS,mode='dynamic',max_hz=1200,min_hz=120,custom={'keep':7});original=json.dumps(source).encode();(root/'settings.json').write_bytes(original)
            evo=initialize(root,'ac_evo');value=json.loads((evo/'settings.json').read_text());self.assertEqual(value,{**source,'draw_mode':'manual','draw_hz':60});self.assertEqual((root/'settings.json').read_bytes(),original)
            value['draw_hz']=90;(evo/'settings.json').write_text(json.dumps(value));initialize(root,'ac_evo');self.assertEqual(json.loads((evo/'settings.json').read_text())['draw_hz'],90)


@unittest.skipUnless(os.name=='nt','Native Tk')
class UI(unittest.TestCase):
    def test_hidden_evo_hud_suspends_paint_and_resumes_without_interrupting_full_recording(self):
        import tkinter as tk
        import hud,engine,vehiclehud,endurancehud
        def pump(app,seconds):
            end=time.monotonic()+seconds
            while time.monotonic()<end:app.root.update();time.sleep(.003)
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            root=Path(t);(root/'settings.json').write_text('{"mode":"fixed","fixed_hz":120,"draw_mode":"manual","draw_hz":60}')
            with patch('hud.ROOT',root),patch('engine.ROOT',root),patch('hud.SIMULATOR','ac_evo'),patch('engine.SIMULATOR','ac_evo'),patch('recorder.Recorder._report',staticmethod(lambda path:None)),patch.object(vehiclehud.Panels,'tick',side_effect=AssertionError('Unavailable EVO panels must not wake')),patch.object(endurancehud.Panels,'tick',side_effect=AssertionError('Unavailable EVO panels must not wake')):
                app=hud.App(demo=True);errors=[];app.root.report_callback_exception=lambda *a:errors.append(a)
                try:
                    pump(app,.25);self.assertGreater(app.diagnostics.frames,1);app.root.withdraw();pump(app,.05);frames=app.diagnostics.frames;samples=app.engine.recorder.samples;pump(app,.3)
                    self.assertLessEqual(app.diagnostics.frames-frames,1);self.assertGreater(app.engine.recorder.samples,samples+10)
                    app.root.deiconify();pump(app,.1);self.assertGreater(app.diagnostics.frames,frames);self.assertFalse(errors)
                finally:
                    app.close()
                    while True:
                        try:
                            if not app.root.winfo_exists():break
                            app.root.update();time.sleep(.003)
                        except tk.TclError:break
                folder=app.engine.last_folder;value=json.loads((folder/'session.json').read_text());self.assertEqual(value['status'],'complete');self.assertEqual(value['samples'],value['writer_stats']['written_rows'])


if __name__=='__main__':unittest.main()
