"""Bounded sidecar reuse and selected factual lap lists without telemetry reads."""
import csv,json,math,os,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT)]


class Data(unittest.TestCase):
    def test_valid_headers_are_isolated_and_physical_changes_invalidate_hits(self):
        import analysis_headers as h
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            folder=Path(t);source=folder/'session_analysis.json';source.write_text('{"laps":[]}',encoding='utf-8')
            value=dict(laps=[dict(number=2,time_s=100.12345678901234,zero=-0.,conditions={'fuel':None})],recent_stability={'n':2**80},stable_reference_file='圈.json')
            h.save(folder,value);side=folder/'analysis_index.json';before={p:p.read_bytes() for p in (source,side)};h._cache.clear()
            first=h.load(folder);self.assertEqual(first,value);first['laps'][0]['conditions']['fuel']=10
            with patch.object(h,'read_json',side_effect=AssertionError('No repeated sidecar read')),patch.object(h,'_read',side_effect=AssertionError('No analysis scan')):
                result=h.load(folder)
            self.assertEqual(result,value);self.assertLess(math.copysign(1,result['laps'][0]['zero']),0)
            for p,data in before.items():self.assertEqual(p.read_bytes(),data)
            # A replaced file with identical size and mtime must still invalidate.
            stamp=side.stat();changed=json.loads(side.read_text('utf-8'));changed['headers']['laps'][0]['number']=9
            replacement=folder/'replacement.json';replacement.write_text(json.dumps(changed,ensure_ascii=False,indent=2),encoding='utf-8')
            # Preserve the original serialization, changing only the single digit.
            replacement.write_bytes(side.read_bytes().replace(b'"number": 2',b'"number": 9'))
            self.assertNotEqual(replacement.read_bytes(),side.read_bytes());os.utime(replacement,ns=(stamp.st_atime_ns,stamp.st_mtime_ns));os.replace(replacement,side)
            self.assertEqual(side.stat().st_size,stamp.st_size);self.assertEqual(side.stat().st_mtime_ns,stamp.st_mtime_ns)
            self.assertEqual(h.load(folder)['laps'][0]['number'],9)
            signature=h._signature(folder)
            with patch.object(h,'_signature',side_effect=[signature,signature+(('changed',None),)]),self.assertRaises(OSError):h.load(folder)
            source.unlink();self.assertEqual(h.load(folder),{});source.mkdir();self.assertEqual(h.load(folder),{})

    def test_sidecar_sample_shapes_and_oversize_are_returned_without_retention(self):
        import analysis_headers as h
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            folder=Path(t);(folder/'session_analysis.json').write_text('{"laps":[]}',encoding='utf-8')
            for extra in ({'profile':[[1,None,-0.]]},{'conditions':{'readings':[1,2,3]}},{'note':'x'*(h._MAX_BYTES+1)}):
                value=dict(laps=[dict(number=1,**extra)],recent_stability={},stable_reference_file=None)
                h.save(folder,value)
                # save() intentionally removes known sample fields; insert legacy shapes directly.
                side=folder/'analysis_index.json';indexed=json.loads(side.read_text('utf-8'));indexed['headers']=value;side.write_text(json.dumps(indexed),encoding='utf-8');h._cache.clear()
                with patch.object(h,'read_json',wraps=h.read_json) as reads:
                    self.assertEqual(h.load(folder),value);self.assertEqual(h.load(folder),value);self.assertEqual(reads.call_count,2)
                self.assertFalse(h._cache)


@unittest.skipUnless(os.name=='nt','Native Windows Tk')
class UI(unittest.TestCase):
    def test_review_retains_only_eight_filters_and_neutralizes_legacy_views_in_both_games(self):
        script=r'''
import json,sys,time,traceback
from datetime import datetime,timezone,timedelta
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'src'))
from unittest.mock import patch
from control_center import ControlCenter
from event_filters import DEFAULTS
errors=[]
with patch.object(ControlCenter,'repair_windows_entry'):
 app=ControlCenter();app.root.geometry('1100x900');app.root.report_callback_exception=lambda *a:errors.append(''.join(traceback.format_exception(*a)))
 def pump(s=.2):
  end=time.monotonic()+s
  while time.monotonic()<end:app.root.update();time.sleep(.005)
 app.review_filter_state={'weather':'wet'};app.show_page(1);pump(.5);c=app.review_filters
 kept={'track','vehicle_class','car','phase','mode','period','outcome','favorite'}
 assert set(c.choices)-{'sort'}==kept and len(c.tiles)==8 and c.toggle_button is None and not c.advanced.winfo_children()
 assert all(c.state[k]==DEFAULTS[k] for k in DEFAULTS if k not in kept and k!='sort') and c.state['sort']==1
 assert '采样缺口待检查' not in c.views and not c.advanced.winfo_manager()
 now=datetime.now(timezone.utc)
 values=[dict(track='Monza',vehicle='BMW M4 LMGT3',vehicle_class='LMGT3',phase='Race',race_mode='online',favorite=True,date=now.isoformat(),_facets={'outcome':'finished','trust':'telemetry','finish_class':1}),dict(track='Fuji',vehicle='Porsche',vehicle_class='LMGT3',phase='Practice',race_mode='single',favorite=False,date=(now-timedelta(days=60)).isoformat()),dict(track='Monza',vehicle='Ferrari',vehicle_class='Hypercar',phase='Race',race_mode='online',favorite=False,date=now.isoformat())]
 assert len(c.pairs(values))==3
 for key,value,count in [('track','Fuji',1),('vehicle_class','LMGT3',2),('car','Porsche',1),('phase','Practice',1),('mode','single',1),('period',1,2),('outcome','winner',1),('favorite','yes',1)]:
  c.reset();c.update_options(values);c.variables[key].set(next(label for label,v in c.lookup[key].items() if v==value));c.apply();assert len(c.pairs(values))==count,(key,c.state)
 c.view.set('Legacy mixed');c.restore();assert c.state['phase']=='Race' and c.state['layout']=='' and c.state['weather']=='' and c.state['start']=='' and len(c.pairs(values))==2
 saved=json.loads(c.path.read_text('utf-8'));assert saved['views']['Legacy mixed']['weather']=='wet' and saved['states']['personal_filter_state']['weather']=='dry'
 c.reset();c.toggle();assert not c.advanced.winfo_manager()
 app.set_theme('light');app.toggle_language();app.root.minsize(800,650);app.root.geometry('900x760');pump(.4);c=app.review_filters
 assert set(c.choices)-{'sort'}==kept and len(c.tiles)==8 and c.toggle_button is None
 assert all(tile.winfo_rootx()+tile.winfo_width()<=c.winfo_rootx()+c.winfo_width()+1 for tile in c.tiles)
 assert c.choices['favorite'].values[0]=='All favourites' or c.choices['favorite'].values[0]=='All favorites',c.choices['favorite'].values
 assert not errors,errors;app.request_close();pump(.1)
'''
        for simulator in ('lmu','ac_evo'):
            with self.subTest(simulator=simulator),tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
                data=Path(t) if simulator=='lmu' else Path(t)/'Simulators/ac_evo';path=data/'EventCatalog/views.json';path.parent.mkdir(parents=True)
                old=dict(layout='old-layout',quality='gaps',start='invalid date',fuel_min='not a number',sort=1)
                path.write_text(json.dumps(dict(states={'review_filter_state':old,'personal_filter_state':{'weather':'dry'}},views={'Legacy mixed':dict(phase='Race',weather='wet',layout='old-layout',start='invalid date')})),encoding='utf-8')
                env=dict(os.environ,LMU_STINTRIX_DATA_DIR=t,STINTRIX_SIMULATOR=simulator,LMU_STINTRIX_HOTKEYS='0',PYTHONIOENCODING='utf-8')
                result=subprocess.run([sys.executable,'-c',script],cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',timeout=35,creationflags=0x08000000)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_selected_timing_list_uses_click_snapshot_order_and_all_evidence_states(self):
        script=r'''
import csv,sys,time,traceback
from pathlib import Path
sys.path[:0]=[str(Path.cwd()/'src'),str(Path.cwd())]
from unittest.mock import patch
from control_center import ControlCenter
from control_evo_lap_overview import show
errors=[]
with patch.object(ControlCenter,'repair_windows_entry'):
 app=ControlCenter();app.root.withdraw();app.root.report_callback_exception=lambda *a:errors.append(''.join(traceback.format_exception(*a)))
 def pump(s=.2):
  end=time.monotonic()+s
  while time.monotonic()<end:app.root.update();time.sleep(.005)
 w=show(app,app.data_path/'Logs/evo');w.geometry('1000x820');pump(.7);c=w.lap_overview;table=c['table'];menu=c['run_menu'];state=c['state'];dest=app.data_path/'exports'
 action=next(a for a in menu.actions if a.key=='timing-selected');assert not action.enabled()
 c['sort']('time',True);keys=tuple(table.order[:9]);table.selection_set(keys);pump(.1)
 expected=[state['rows'][k]['lap']['num'] for k in table.selection()];assert len(expected)==9 and action.enabled() and not c['buttons']['csv'].enabled
 assert any(not state['rows'][k]['usable'] for k in keys)
 with patch('tkinter.filedialog.askdirectory',return_value=''),patch.object(app,'run_background',side_effect=AssertionError('Cancelled')):menu.invoke('timing-selected')
 assert not state['loading'] and getattr(app,'lap_curve_jobs',0)==0
 jobs=[]
 def destination(**kw):
  assert '已选 9 圈' in kw['title'];table.selection_set(('1',));return str(dest)
 with patch('tkinter.filedialog.askdirectory',side_effect=destination),patch.object(app,'run_background',side_effect=lambda work,done:jobs.append((work,done))):menu.invoke('timing-selected')
 assert len(jobs)==1 and app.lap_curve_jobs==1 and not action.enabled()
 with patch('evo_laps.index',side_effect=AssertionError('No index scan')),patch('lap_scan_index.raw_rows',side_effect=AssertionError('No samples')),patch('evo_laps.read_curve',side_effect=AssertionError('No curves')):result=jobs[0][0]()
 with Path(result['path']).open(encoding='utf-8-sig',newline='') as stream:rows=list(csv.DictReader(stream))
 assert [int(r['lap']) for r in rows]==expected and result['rows']==9
 assert any(r['valid']=='False' and r['eligible_for_export']=='False' for r in rows)
 assert any(r['valid']=='' and r['eligible_for_export']=='False' for r in rows)
 jobs[0][1](result,None);jobs[0][1](result,None);assert app.lap_curve_jobs==0 and table.selection()==('1',) and not state['loading']
 app.set_theme('light');app.toggle_language();w.geometry('800x600');pump(.2);c['buttons']['run'].invoke();pump(.2);menu.hover('timing-selected')
 assert 'without full telemetry' in menu.footer.cget('text') and menu.popup.winfo_rootx()+menu.popup.winfo_width()<=w.winfo_rootx()+w.winfo_width()+1
 menu.close(False);table.selection_set(());pump(.1);assert not action.enabled()
 w.destroy();assert not errors,errors;app.request_close();pump(.1)
'''
        from tests.test_processing329 import fixture
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            folder=fixture(Path(t)/'Simulators/ac_evo',laps=10);path=folder/'inputs.csv'
            with path.open(encoding='utf-8',newline='') as stream:r=csv.DictReader(stream);fields=r.fieldnames;rows=list(r)
            for row in rows:
                if row['lap']=='4':row['lap_invalidated']='1'
                if row['lap']=='6':row['lap_invalidated']=''
            with path.open('w',encoding='utf-8',newline='') as stream:w=csv.DictWriter(stream,fieldnames=fields);w.writeheader();w.writerows(rows)
            before={p:p.read_bytes() for p in (path,folder/'session.json')};env=dict(os.environ,LMU_STINTRIX_DATA_DIR=t,STINTRIX_SIMULATOR='ac_evo',LMU_STINTRIX_HOTKEYS='0',PYTHONIOENCODING='utf-8')
            result=subprocess.run([sys.executable,'-c',script],cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',timeout=35,creationflags=0x08000000)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            for p,data in before.items():self.assertEqual(p.read_bytes(),data)
