"""Numeric-only computation, EVO PB history and reusable curve provenance."""
import csv,json,math,os,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))


def events(root):
    from tests.test_evo_records310 import fixture
    base=fixture(root)
    for name,seconds,date in [('faster',19,'2026-10-27T11:00:00Z'),('slower',21,'2026-10-27T12:00:00Z')]:
        folder=root/'Logs'/name;shutil.copytree(base,folder);meta=json.loads((folder/'session.json').read_text());meta['started_utc']=date;(folder/'session.json').write_text(json.dumps(meta))
        with (folder/'inputs.csv').open(newline='',encoding='utf-8') as f:r=csv.DictReader(f);fields=r.fieldnames;rows=list(r)
        for row in rows:
            for key in ('time_s','evo_lap_time_ms','evo_last_lap_time_ms'):row[key]=str(float(row[key])*seconds/20)
        with (folder/'inputs.csv').open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    return base


class Processing(unittest.TestCase):
    def test_numeric_view_preserves_missing_signed_zero_slices_and_all_computations(self):
        from analysis_spool import LapRows,numeric_rows,project_rows
        from buffers import CompactRow
        from sessionlab import actions
        from training_zones import features
        from laps import comparison_data
        columns=('session_time_s','lap_distance_m','throttle','brake','steering','filtered_throttle','filtered_brake','filtered_steering','world_x_m','world_z_m','abs_active','tc_active','speed_kmh')
        layout={k:i for i,k in enumerate(columns)}
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            source=LapRows(t)
            for i in range(1001):
                row=[i*.01,i*5,max(0,math.sin(i*.03)),max(0,-math.sin(i*.03)),-0.0 if i==0 else math.sin(i*.02),.543210987654321,.12345678901234567,.1,i*.01,i*.02,math.nan if i%7 else 1,math.nan,173.12345678901234]
                source.append(CompactRow(layout,row,'UTC, "🏁"\r\n'+str(i)))
            source.seal();plain=list(source);selected=numeric_rows(source,columns)
            self.assertEqual([dict(r) for r in source],[dict(r) for r in plain]);self.assertEqual(project_rows(source,columns)[0].utc,plain[0].utc)
            self.assertEqual([r.values[0] for r in numeric_rows(source[13:220:3][::-1],columns)],[r.values[0] for r in plain[13:220:3][::-1]])
            self.assertEqual(math.copysign(1,selected[0]['steering']),-1);self.assertNotIn('tc_active',selected[0])
            expected=actions(plain);feature=features(plain,0,10,5000)
            best=dict(rows=plain,start_s=0,end_s=10,length_m=5000,first_distance_index=0,next_row=plain[-1]);curve=comparison_data(best);expected_curve=list(curve);curve.close()
            with patch.object(source.utc,'read',side_effect=AssertionError('Unneeded UTC decode')),patch('buffers.array',side_effect=AssertionError('Unneeded per-row numeric copy')):
                self.assertEqual(actions(source),expected);self.assertEqual(features(source,0,10,5000),feature)
                curve=comparison_data(dict(best,rows=source));self.assertEqual(list(curve),expected_curve);curve.close()
            source.close()

    def test_evo_history_is_per_model_layout_mode_and_reuses_existing_records(self):
        from record_history import history
        from evo_laps import export
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            root=Path(t)/'Simulators/ac_evo';base=events(root)
            raw={p:p.read_bytes() for p in root.glob('Logs/*/inputs.csv')}
            for folder in root.glob('Logs/*'):export(folder)
            with patch('evo_laps.export',side_effect=AssertionError('Repeated lap extraction')):
                value=history(root,per_vehicle=True)
            self.assertEqual([e['time_s'] for e in value['entries']],[20,19]);self.assertEqual(value['entries'][1]['improvement_s'],1)
            self.assertTrue(all(e['session']['simulator_id']=='ac_evo' for e in value['entries']))
            for p,b in raw.items():self.assertEqual(p.read_bytes(),b)

    def test_curve_reuse_across_views_invalidates_source_assets_and_missing_output(self):
        from personal_records import records
        from curve_exports import save
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            root=Path(t)/'Simulators/ac_evo';events(root);entry=records(root)[0]
            page=save(root,entry);stamp=Path(page).stat().st_mtime_ns
            with patch('evo_laps.write_curve',side_effect=AssertionError('Repeated render')):
                self.assertEqual(save(root,dict(entry)),page);self.assertEqual(Path(page).stat().st_mtime_ns,stamp)
            path=Path(entry['file']);s=path.stat();os.utime(path,ns=(s.st_atime_ns,s.st_mtime_ns+1000000));other=save(root,entry);self.assertNotEqual(other,page)
            Path(other).unlink();self.assertEqual(save(root,entry),other)
            with patch('paths.app_version',return_value='asset-change-fixture'):self.assertNotEqual(save(root,entry),other)
            with self.assertRaises(ValueError):save(Path(t),entry)
            self.assertTrue(Path(page).is_file())


class UI(unittest.TestCase):
    def test_evo_history_tabs_chart_shortcuts_and_rebuild_keep_context(self):
        script=r'''
import sys,time,traceback
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'src'))
from unittest.mock import patch
from control_center import ControlCenter
errors=[]
with patch.object(ControlCenter,'repair_windows_entry'):
 app=ControlCenter();app.root.geometry('1200x850+20+20');app.root.report_callback_exception=lambda *a:errors.append(''.join(traceback.format_exception(*a)))
 def pump(s=.3):
  end=time.monotonic()+s
  while time.monotonic()<end:app.root.update();time.sleep(.005)
 app.show_page(6);pump(1.2);assert set(app.personal_record_tabs)=={'best','history'}
 app.personal_record_tabs['history'].invoke();pump(1);page=app.record_loaders['history'].page
 assert len(page.entries)==2 and 'comparable' not in page.buttons and 'lap-pair' in page.buttons
 assert page.table.displaycolumns==['date','track','layout','car','time','gain']
 assert int(page.table.viewport.cget('height'))==round(page.table.rowheight*2)
 page.query.set('Ferrari');pump();assert len(page.chart.points)==2
 selected=page.selected['folder'];page.buttons['lap-pair'].invoke();pump(.7);assert app.lap_pair_window.pair_controls['state']['rows']['A'];app.lap_pair_window.destroy()
 with patch('control_record_browser.os.startfile') as opened:
  page.curve();pump(1);assert opened.call_count==1
  first=page.exporter.path;page.curve();pump();assert page.exporter.path==first and opened.call_count==2
 app.personal_record_tabs['best'].invoke();pump();app.personal_record_tabs['history'].invoke();pump(.8)
 page=app.record_loaders['history'].page;assert page.query.get()=='Ferrari' and page.selected['folder']==selected
 app.set_theme('light');pump(.8);app.toggle_language();pump(.8);page=app.record_loaders['history'].page
 assert app.personal_record_view=='history' and page.query.get()=='Ferrari' and page.selected['folder']==selected
 assert not errors,errors
 app.request_close();pump(.2)
print('EVO PB history, chart, context, exact curve and A/B shortcut OK')
'''
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            events(Path(t)/'Simulators/ac_evo');env=dict(os.environ,LMU_STINTRIX_DATA_DIR=t,STINTRIX_SIMULATOR='ac_evo',LMU_STINTRIX_HOTKEYS='0',PYTHONIOENCODING='utf-8')
            result=subprocess.run([sys.executable,'-c',script],cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',timeout=40)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)

if __name__=='__main__':unittest.main()
