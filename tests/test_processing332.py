"""Precise report-art repair and reusable personal curves with direct EVO navigation."""
import json,os,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT)]
from tests.test_vehicle_variants330 import fixture,CAR,UNRESTRICTED


def assets(root):
    target=Path(root)/'assets'
    for name in ('compare.html','evo_compare.html','interface_theme.js','dataview.js','laplab.js','trackview.js','vehicleview.js','tracks/catalog.json'):
        p=target/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/'src'/name,p)
    return target


def entry(root,simulator):
    from personal_records import entries
    folder=fixture(root,'record',107.823303)
    if simulator=='ac_evo':
        for name in ('session.json','fastest_lap.lap.json','fastest_lap_summary.json'):
            path=folder/name;value=json.loads(path.read_text('utf-8'))
            value['simulator_id']='ac_evo'
            if 'session' in value and isinstance(value['session'],dict):value['session']['simulator_id']='ac_evo'
            if 'lap' in value:value['lap'].update(boundary_interpolation=False,timing_source='evo_last_laptime_ms')
            path.write_text(json.dumps(value),'utf-8')
        # A valid current summary avoids any raw scan in this fixture.
        from evo_laps import stamp
        path=folder/'fastest_lap_summary.json';v=json.loads(path.read_text('utf-8'));v['signature']=stamp(folder);path.write_text(json.dumps(v),'utf-8')
    return entries(root)[0]


class Data(unittest.TestCase):
    def test_known_alias_repair_backup_idempotence_and_explicit_override(self):
        from race_art import select_car,prepare_renderer_aliases
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            root=Path(t);base=root/'Ferrari 296 LMGT3.png';base.write_bytes(b'local image');path=root/'car_calibration.json'
            value=dict(other='preserve',cars={base.name:dict(aliases=['Ferrari 296 GT3'],subject_bounds=[.1,.2,.8,.9],custom=17)})
            path.write_text(json.dumps(value),'utf-8');original=path.read_bytes()
            self.assertEqual(select_car(CAR,root)[0],base);self.assertEqual(select_car(UNRESTRICTED,root)[0],base)
            self.assertIsNone(select_car('Ferrari mystery prototype',root))
            self.assertEqual(prepare_renderer_aliases(path,root),2);changed=path.read_bytes();stamp=path.stat().st_mtime_ns
            backup=root/'car_calibration.stintrix-aliases-v1.backup.json';self.assertEqual(backup.read_bytes(),original)
            self.assertEqual(prepare_renderer_aliases(path,root),0);self.assertEqual(path.read_bytes(),changed);self.assertEqual(path.stat().st_mtime_ns,stamp)
            v=json.loads(changed);self.assertEqual(v['other'],'preserve');self.assertEqual(v['cars'][base.name]['custom'],17)
            exact=root/'custom.png';exact.write_bytes(b'explicit custom image');v['cars'][base.name]['aliases'].remove(UNRESTRICTED);v['cars'][exact.name]=dict(aliases=[UNRESTRICTED],subject_bounds=[0,0,1,1]);path.write_text(json.dumps(v),'utf-8')
            self.assertEqual(prepare_renderer_aliases(path,root),0);self.assertEqual(select_car(UNRESTRICTED,root)[0],exact)
            self.assertEqual(backup.read_bytes(),original)

    def test_personal_curve_reuses_after_version_and_copy_times_both_games(self):
        from curve_exports import save
        for simulator in ('lmu','ac_evo'):
            with self.subTest(simulator=simulator),tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
                root=Path(t) if simulator=='lmu' else Path(t)/'Simulators/ac_evo';e=entry(root,simulator);copied=assets(t)
                with patch('paths.ASSETS',copied),patch('paths.track_catalog_path',return_value=copied/'tracks/catalog.json'):
                    page=Path(save(root,e));body=page.read_bytes();modified=page.stat().st_mtime_ns
                    for path in copied.rglob('*'):
                        if path.is_file():s=path.stat();os.utime(path,ns=(s.st_atime_ns,s.st_mtime_ns+1000000000))
                    with patch('paths.app_version',return_value='99.9.99'),patch('json_store.load',side_effect=AssertionError('Cached curve must not parse samples')):
                        self.assertEqual(Path(save(root,e)),page)
                    self.assertEqual(page.read_bytes(),body);self.assertEqual(page.stat().st_mtime_ns,modified)
                    # New renderer content produces a distinct page, retaining the old one.
                    with (copied/'interface_theme.js').open('a',encoding='utf-8') as stream:stream.write('\n// fixture renderer update\n')
                    updated=Path(save(root,e));self.assertNotEqual(updated,page);self.assertEqual(page.read_bytes(),body)

    def test_curve_signature_tracks_sources_caption_revision_theme_and_language(self):
        import curve_exports,i18n
        from control_theme import T
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            e=entry(Path(t),'lmu');first=curve_exports.signature(e)
            for key,value in (('vehicle',UNRESTRICTED),('driver','Corrected driver')):
                changed={**e,'session':{**e['session'],key:value}};self.assertNotEqual(curve_exports.signature(changed),first)
            with patch.object(curve_exports,'CURVE_REVISION',2):self.assertNotEqual(curve_exports.signature(e),first)
            import control_theme
            with patch.dict(control_theme.PALETTES,fixture_palette={'BG':'#123456'}):self.assertNotEqual(curve_exports.signature(e),first)
            with patch.object(T,'mode','light' if T.mode=='dark' else 'dark'):self.assertNotEqual(curve_exports.signature(e),first)
            with patch.object(i18n,'language','en' if i18n.language=='zh' else 'zh'):self.assertNotEqual(curve_exports.signature(e),first)
            for name in ('file','folder'):
                p=Path(e['file']) if name=='file' else Path(e['folder'])/'session.json';s=p.stat();os.utime(p,ns=(s.st_atime_ns,s.st_mtime_ns+1000000))
                self.assertNotEqual(curve_exports.signature(e),first);os.utime(p,ns=(s.st_atime_ns,s.st_mtime_ns))


@unittest.skipUnless(os.name=='nt','Native Windows Tk')
class UI(unittest.TestCase):
    def test_evo_records_and_history_open_same_overview_without_losing_context(self):
        script=r"""
import sys,time,traceback
from pathlib import Path
sys.path[:0]=[str(Path.cwd()/'src'),str(Path.cwd())]
from unittest.mock import patch
from control_center import ControlCenter
errors=[]
with patch.object(ControlCenter,'repair_windows_entry'):
 app=ControlCenter();app.root.geometry('1200x850');app.root.report_callback_exception=lambda *a:errors.append(''.join(traceback.format_exception(*a)))
 def pump(condition=lambda:True,seconds=7):
  end=time.monotonic()+seconds
  while time.monotonic()<end:
   app.root.update();time.sleep(.01)
   if condition():return
  raise AssertionError('Native page did not settle')
 app.show_page(6);pump(lambda:app.record_loaders.get('best') and app.record_loaders['best'].page and app.record_loaders['best'].page.selected is not None)
 best=app.record_loaders['best'].page;chosen=best.selected['folder'];best.query.set('Ferrari');best.populate_best();pump()
 with patch.object(app,'active',return_value=True):best.lap_overview();assert not getattr(app,'evo_lap_windows',{})
 best.menu.invoke('lap-overview');pump(lambda:bool(getattr(app,'evo_lap_windows',{})))
 window=next(iter(app.evo_lap_windows.values()));pump(lambda:window.lap_overview['state']['result'] is not None)
 assert str(window.lap_overview['folder'])==chosen
 window.lap_overview['kind'].set('valid');window.lap_overview['query'].set('2');window.lap_overview['populate']()
 before=(best.query.get(),best.selected['folder']);best.lap_overview();pump()
 assert len(app.evo_lap_windows)==1 and window.lap_overview['query'].get()=='2'
 assert (best.query.get(),best.selected['folder'])==before
 app.personal_record_tabs['history'].invoke();pump(lambda:app.record_loaders.get('history') and app.record_loaders['history'].page and app.record_loaders['history'].page.selected is not None)
 history=app.record_loaders['history'].page;assert 'lap-overview' in history.buttons
 history.buttons['lap-overview'].invoke();pump();assert len(app.evo_lap_windows)==1
 app.set_theme('light');app.toggle_language();pump();assert not errors,errors
 window.destroy();app.request_close();pump()
"""
        from tests.test_processing329 import fixture as recorded
        from evo_laps import export
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            folder=recorded(Path(t)/'Simulators/ac_evo');export(folder);before={p:p.read_bytes() for p in (folder/'inputs.csv',folder/'session.json')}
            env=dict(os.environ,LMU_STINTRIX_DATA_DIR=t,STINTRIX_SIMULATOR='ac_evo',LMU_STINTRIX_HOTKEYS='0',PYTHONIOENCODING='utf-8')
            result=subprocess.run([sys.executable,'-c',script],cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',timeout=25,creationflags=0x08000000)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            for p,b in before.items():self.assertEqual(p.read_bytes(),b)
