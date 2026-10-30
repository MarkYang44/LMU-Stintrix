"""EVO native activity/instruments: single reader, exact storage and cached HUD."""
import csv,io,json,math,os,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))


def driving(packet=1):
    from tests.test_simulators import frame
    from acevo import extract
    p,g,s,_=frame(packet)
    p.gear=6;p.rpms=6111;p.currentMaxRpm=9100;p.absInAction=7;p.tcinAction=0
    g.gear_int=4;g.rpm=7234;g.rpm_percent=.87654321
    g.abs_active=False;g.tc_active=True;g.esc_active=bool(packet%2);g.is_change_up_rpm=True
    return p,g,s,extract(p,g,s,time.monotonic())


class Data(unittest.TestCase):
    def test_native_sources_and_exact_record_compression_archive_roundtrip(self):
        from acevo import extract,EXTRA,DRIVING_COLUMNS
        from app_config import COLUMNS
        from recorder import Recorder
        from column_store import convert
        from telemetry_file import Path as TelemetryPath
        from session_archive import export_session,import_session
        from evo_driving import instruments
        p,g,s,value=driving();before=tuple(map(bytes,(p,g,s)))
        self.assertEqual(value['native']['evo_abs_active'],0) # Not OR'ed with physics 7.
        self.assertEqual(value['native']['evo_physics_abs_active'],7)
        self.assertEqual(value['native']['evo_rpm_percent'],float(g.rpm_percent))
        self.assertEqual(instruments(value)['gear'],'3');self.assertEqual(instruments(value)['rpm'],'7234')
        self.assertTrue(instruments(value)['up']);self.assertEqual(tuple(map(bytes,(p,g,s))),before)
        self.assertEqual(len(set((*COLUMNS,*EXTRA))),len(COLUMNS)+len(EXTRA))
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as temp:
            base=Path(temp);root=base/'Simulators/ac_evo';root.mkdir(parents=True)
            with patch.object(Recorder,'_report',staticmethod(lambda folder:None)):
                recorder=Recorder(root/'Logs');recorder.start(value)
                expected=[]
                for packet in range(60):
                    p,g,s,v=driving(packet);g.rpm_percent=-0.0 if packet==2 else float('nan') if packet==3 else g.rpm_percent
                    v=extract(p,g,s,value['et']+packet*.001234567890123)
                    if packet==4:
                        v=dict(v,native={k:n for k,n in v['native'].items() if k not in DRIVING_COLUMNS})
                    expected.append(v);self.assertTrue(recorder.add(v))
                recorder.finish('manual stop')
                for worker in recorder.pending_reports:worker.join(5)
            source=recorder.folder/'inputs.csv';original=source.read_bytes();rows=list(csv.DictReader(io.StringIO(original.decode('utf-8-sig'))))
            self.assertEqual(len(rows),60)
            for row,sample in zip(rows,expected):
                for key in EXTRA:self.assertEqual(row[key],str(sample['native'].get(key,'')))
                self.assertEqual(float(row['throttle']),sample['controls'][0]);self.assertEqual(row['session_time_s'],'')
            self.assertEqual(rows[2]['evo_rpm_percent'],'-0.0');self.assertEqual(rows[3]['evo_rpm_percent'],'nan')
            meta=json.loads((recorder.folder/'session.json').read_text('utf-8'))
            self.assertEqual(meta['samples'],meta['writer_stats']['written_rows']);self.assertIn('driving_channels',meta)
            convert(source,replace=True);self.assertEqual(TelemetryPath(source).read_bytes(),original)
            package=export_session(root,str(recorder.folder.relative_to(root)),base/'exports')['path']
            restored=Path(import_session(base/'restored/Simulators/ac_evo',package,verify=True)['folder'])
            self.assertEqual(TelemetryPath(restored/'inputs.csv').read_bytes(),original)

    def test_activity_edges_keep_short_pulses_break_gaps_and_bound_memory(self):
        from evo_driving import ActivityHistory,marker_segments,instruments
        history=ActivityHistory()
        def add(t,a=0):history.add(t,dict(evo_abs_active=a,evo_tc_active=0,evo_esc_active=0))
        add(0);add(.005,1);add(.006);add(1)
        spans=marker_segments(history.snapshot(-2),1,3,0,600)
        self.assertEqual(len(spans[0]),1);self.assertGreaterEqual(spans[0][0][1]-spans[0][0][0],1)
        add(2,1);add(8,1);add(9)
        spans=marker_segments(history.snapshot(-2),9,12,0,600)[0]
        self.assertEqual(len(spans),3);self.assertLess(spans[1][1],spans[2][0])
        history.clear()
        for i in range(10000):add(i/120)
        self.assertEqual(len(history.edges),1);self.assertLess(len(history.edges._data)*8,4096)
        self.assertEqual(instruments(None)['gear'],'—');self.assertTrue(all(math.isnan(v) for v in instruments(None)['activity']))
        for gear,text in ((0,'R'),(1,'N'),(2,'1'),(8,'7'),(-1,'—')):
            self.assertEqual(instruments({'native':{'evo_gear':gear}})['gear'],text)
        self.assertIsNone(instruments({'native':{'evo_rpm_percent':float('nan')}})['fraction'])
        history.clear();self.assertEqual(history.snapshot(0),((),None))


@unittest.skipUnless(os.name=='nt','Native Tk HUD')
class UI(unittest.TestCase):
    def test_single_capture_live_toggles_modes_themes_and_unknowns(self):
        import hud,engine,tkinter as tk,control_theme
        class Reader:
            created=0;reads=0;closed=0
            def __init__(self):Reader.created+=1
            def read(self):
                Reader.reads+=1;return driving(Reader.reads)[3]
            def close(self):Reader.closed+=1
        def pump(app,seconds=.12):
            end=time.monotonic()+seconds
            while time.monotonic()<end:app.root.update();time.sleep(.003)
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as temp:
            root=Path(temp)/'Simulators/ac_evo';root.mkdir(parents=True)
            (root/'settings.json').write_text('{"mode":"fixed","fixed_hz":120,"draw_mode":"manual","draw_hz":60}')
            with patch('hud.ROOT',root),patch('engine.ROOT',root),patch('hud.SIMULATOR','ac_evo'),patch('engine.SIMULATOR','ac_evo'),patch('simulators.reader_factory',return_value=Reader),patch('recorder.Recorder._report',staticmethod(lambda folder:None)):
                app=hud.App();errors=[];app.root.report_callback_exception=lambda *a:errors.append(a)
                try:
                    pump(app,.3);owner=app.engine;recorder=owner.recorder;folder=recorder.folder;count=recorder.samples
                    self.assertEqual(app.canvas.itemcget(app.live_items['evo_gear'][0],'text'),'3')
                    self.assertEqual(app.canvas.itemcget(app.live_items['evo_rpm'][0],'text'),'7234 RPM')
                    self.assertNotIn('evo_speed',app.live_items)
                    self.assertTrue(any(k.startswith('evo_mark_1_') for k in app.live_items))
                    ids={k:v[0] for k,v in app.live_items.items() if k.startswith('evo_')};pump(app)
                    self.assertEqual(ids['evo_gear'],app.live_items['evo_gear'][0])
                    app.set_evo_hud('assists',False);pump(app);self.assertFalse(any(k.startswith('evo_mark_') for k in app.live_items))
                    app.set_evo_hud('instruments',False);pump(app);self.assertNotIn('evo_band',app.live_items)
                    app.set_evo_hud('assists',True);app.set_evo_hud('instruments',True);pump(app)
                    for mode in ('controls','curves','normal'):
                        app.hud_mode.set(mode);app.apply_clean_mode();pump(app)
                        self.assertIn('evo_gear',app.live_items)
                        bounds=app.canvas.bbox(app.live_items['evo_gear'][0]);self.assertGreaterEqual(bounds[1],0);self.assertLessEqual(bounds[3],app.canvas.winfo_height())
                    control_theme.set_mode('light');app.apply_theme();app.root.geometry('440x170');pump(app)
                    self.assertEqual(app.canvas.itemcget(app.live_items['evo_rpm'][0],'fill'),control_theme.T.FG)
                    self.assertIs(owner,app.engine);self.assertIs(recorder,owner.recorder);self.assertEqual(folder,recorder.folder)
                    self.assertGreater(recorder.samples,count+20);self.assertEqual(Reader.created,1);self.assertFalse(errors)
                    self.assertEqual(len(list((root/'Logs').iterdir())),1)
                finally:
                    app.close()
                    deadline=time.monotonic()+8
                    while time.monotonic()<deadline:
                        try:
                            if not app.root.winfo_exists():break
                            app.root.update();time.sleep(.003)
                        except tk.TclError:break
                    control_theme.set_mode('dark')
                self.assertFalse(owner.thread.is_alive());self.assertEqual(Reader.closed,1)
                meta=json.loads((folder/'session.json').read_text('utf-8'));self.assertEqual(meta['samples'],meta['writer_stats']['written_rows'])
            from control_center import ControlCenter
            from control_widgets import Switch
            import i18n
            with patch('control_center.ROOT',root),patch('control_center.SIMULATOR','ac_evo'),patch.object(ControlCenter,'repair_windows_entry'):
                center=ControlCenter();center.root.report_callback_exception=lambda *a:errors.append(a)
                try:
                    pump(center);self.assertEqual(set(center.evo_hud_vars),{'assists','instruments'})
                    def walk(w):
                        for child in w.winfo_children():yield child;yield from walk(child)
                    switches=[w for w in walk(center.content) if isinstance(w,Switch) and w.variable in tuple(center.evo_hud_vars.values())]
                    self.assertEqual(len(switches),2)
                    for switch in switches:
                        switch.toggle();pump(center);self.assertFalse(switch.variable.get())
                        self.assertFalse(json.loads((root/'evo_hud.json').read_text())[next(k for k,v in center.evo_hud_vars.items() if v is switch.variable)])
                    i18n.set_language('en');i18n.refresh(center.root);pump(center)
                    self.assertEqual(i18n.tr('EVO 驾驶信息'),'EVO driving information');self.assertFalse(errors)
                finally:
                    center.close();i18n.set_language('zh')


if __name__=='__main__':unittest.main()
