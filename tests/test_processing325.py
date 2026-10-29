"""EVO scan equivalence and direct export of selected A/B lap identities."""
import csv,hashlib,json,math,os,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))


def record(root,kind='normal'):
    from tests.test_evo_records310 import fixture
    folder=fixture(root);path=folder/'inputs.csv'
    with path.open(encoding='utf-8',newline='') as source:reader=csv.DictReader(source);fields=reader.fieldnames;rows=list(reader)
    for i,row in enumerate(rows):
        if kind=='filled':row.update(evo_current_pos=str(i//30%3+1),evo_total_drivers='12')
        if kind=='legacy':row['evo_last_lap_time_ms']=''
        if kind=='unusual':
            if i==130:row['lap_distance_m']='NaN'
            if i==140:row['evo_current_pos']='Infinity'
            if i==145:row['evo_total_drivers']='bad'
        if kind=='valid':row['lap_invalidated']='0'
    with path.open('w',encoding='utf-8',newline='') as out:writer=csv.DictWriter(out,fieldnames=fields);writer.writeheader();writer.writerows(rows)
    return folder


class Data(unittest.TestCase):
    def test_record_inventory_reuses_current_metadata_without_changing_game_or_overrides(self):
        from personal_records import entries
        from evo_laps import export
        from tests.test_evo_records310 import fixture
        from race_mode_overrides import save
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            base=Path(t);game=base/'Simulators/ac_evo';evo=fixture(game);export(evo)
            lmu=base/'Logs/lmu';lmu.mkdir(parents=True)
            meta=dict(status='complete',track='LMU track',vehicle='BMW M4 LMGT3',started_utc='2026-10-28T10:00:00Z')
            (lmu/'session.json').write_text(json.dumps(meta),'utf-8');(lmu/'lap.json').write_text('{}','utf-8')
            lap=dict(number=2,time_s=100.12345678901234,track_length_m=5000.123456789,validity='verified')
            (lmu/'fastest_lap_summary.json').write_text(json.dumps(dict(status='saved',file='lap.json',lap=lap,conditions={'fuel_l':12.123456789})),'utf-8')
            save(game,[evo],'online');before={p:p.read_bytes() for p in (evo/'session.json',lmu/'session.json')}
            with patch('personal_records.load',side_effect=AssertionError('No duplicate metadata read')):
                a=entries(base);b=entries(game)
            self.assertEqual(len(a),1);self.assertEqual(len(b),1);self.assertEqual(a[0]['time_s'],lap['time_s']);self.assertEqual(a[0]['length_m'],lap['track_length_m'])
            self.assertEqual(b[0]['race_mode'],'online');self.assertEqual(b[0]['session']['simulator_id'],'ac_evo')
            for p,body in before.items():self.assertEqual(p.read_bytes(),body)
            meta['vehicle']='Porsche 911 GT3 R LMGT3';(lmu/'session.json').write_text(json.dumps(meta),'utf-8')
            self.assertEqual(entries(base)[0]['session']['vehicle'],meta['vehicle'])

    def test_numeric_rows_preserve_sparse_nonfinite_tokens_and_signed_zero(self):
        from evo_laps import _numbers
        cases=[(('0','-0.0','1e-250','1e250','','NaN','Infinity','bad',None,' 5 '),[0.,-0.,1e-250,1e250,None,None,None,None,None,5.]),
            (('1.2345678901234567',)*10,[1.2345678901234567]*10),
            ((None,'',False,True,0,1,'-Infinity','   ','0x1','1e999'),[None,None,0.,1.,0.,1.,None,None,None,None])]
        for row,expected in cases:self.assertEqual(_numbers(row),expected)
        self.assertLess(math.copysign(1,_numbers(cases[0][0])[1]),0)

    def test_scan_matches_previous_complete_results_and_packed_source(self):
        from evo_laps import scan
        from column_store import convert
        # Complete golden scan outputs from v0.3.24, including boundaries,
        # validity, gaps, position events, exact times and seek cookies.
        expected=dict(normal='44f82bfa9fa49bbfc0140a8e7313802d93e42a73dcbf4339dbb09ce3dfd242b6',
            filled='0c4162ebca093acdaad7fbf9222035db0a6048828cb035f52867d2e026ce56fa',
            legacy='e64cb7bb07882c47a0b20d997b46379e940f5dca3a5ffbf8968c5909f6d2f580',
            unusual='e2fe78693a5b60a5881d039b8ecc6f793b2103b92fa1e0d7c9b681256858a2a3')
        self.assertEqual(len(expected),4)
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            for kind,digest in expected.items():
                folder=record(Path(t)/kind,kind);raw=(folder/'inputs.csv').read_bytes();value=scan(folder)
                encoded=json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
                self.assertEqual(hashlib.sha256(encoded).hexdigest(),digest,kind)
                self.assertEqual((folder/'inputs.csv').read_bytes(),raw)
                self.assertTrue(convert(folder/'inputs.csv',replace=True)['converted']);packed=scan(folder)
                self.assertEqual({k:v for k,v in packed.items() if k!='cookies'},{k:v for k,v in value.items() if k!='cookies'},kind)
                self.assertEqual(packed['cookies'],[])

    def test_selected_csv_uses_requested_nonfastest_lap_and_rejects_bad_identity(self):
        from evo_exports import lap_csv,fastest_csv
        from evo_laps import index
        from lap_scan_index import raw_rows
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            root=Path(t)/'Simulators/ac_evo';folder=record(root,'valid');value=index(folder);self.assertEqual(value['fastest']['num'],2)
            with (folder/'inputs.csv').open(encoding='utf-8',newline='') as stream:fields=next(csv.reader(stream))
            lap=next(v for v in value['laps'] if v['num']==3);expected=io_text(fields,raw_rows(folder/'inputs.csv',lap['first_index'],lap['end_index'],value['cookies'],columns=fields))
            before={p:p.read_bytes() for p in (folder/'session.json',folder/'inputs.csv')};dest=Path(t)/'exports'
            with patch('evo_laps.read_curve',side_effect=AssertionError('No curve needed')),patch('evo_laps.write_curve',side_effect=AssertionError('No page needed')):
                result=lap_csv(root,folder,dest,number=3);best=fastest_csv(root,folder,dest)
            self.assertEqual(result['number'],3);self.assertEqual(best['number'],2);self.assertEqual(Path(result['path']).read_bytes(),expected)
            for number in (True,0,-1,'3',1000):
                with self.assertRaises(ValueError):lap_csv(root,folder,dest,number=number)
            invalid=record(root/'source-invalid','normal')
            with self.assertRaises(ValueError):lap_csv(root,invalid,dest,number=3)
            self.assertEqual(len(list(dest.glob('*.csv'))),2);self.assertFalse(list(dest.glob('*.pending')))
            self.assertFalse((folder/'SelectedLaps').exists())
            for p,body in before.items():self.assertEqual(p.read_bytes(),body)


def io_text(fields,rows):
    import io
    out=io.StringIO(newline='');writer=csv.writer(out);writer.writerow(fields);writer.writerows(rows);return out.getvalue().encode('utf-8')


@unittest.skipUnless(os.name=='nt','Native Windows Tk')
class UI(unittest.TestCase):
    def test_evo_pair_csv_keeps_roles_snapshots_and_bilingual_small_layout(self):
        script=r'''
import sys,time,traceback
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'src'))
from unittest.mock import patch
from control_center import ControlCenter
from control_lap_pair import show
from control_evo_exports import selected_csv
errors=[]
with patch.object(ControlCenter,'repair_windows_entry'):
 app=ControlCenter();app.root.geometry('1200x850');app.root.report_callback_exception=lambda *a:errors.append(''.join(traceback.format_exception(*a)))
 def pump(s=.3):
  end=time.monotonic()+s
  while time.monotonic()<end:app.root.update();time.sleep(.005)
 folder=app.data_path/'Logs/evo';w=show(app,app.data_path,[folder]);w.geometry('880x700');pump(.7);c=w.pair_controls
 assert c['csv'] is not None and not c['csv'].enabled
 c['quick']['same'].invoke();pump(.1)
 def choose(key,number):c['numbers'][key].set(next(label for label,n in c['state']['laps'][key].items() if n==number));c['refresh']()
 choose('A',3);choose('B',2);assert c['csv'].enabled
 wanted={k:(c['events'][k].get(),c['numbers'][k].get()) for k in ('A','B')}
 with patch.object(app,'active',return_value=True),patch('control_evo_exports.filedialog.askdirectory') as pick:
  c['csv'].invoke();pick.assert_not_called()
 assert 'HUD' in c['status'].get()
 def pick(**kw):choose('A',2);choose('B',3);return str(app.data_path/'exports')
 with patch('control_evo_exports.filedialog.askdirectory',side_effect=pick),patch('evo_laps.read_curve',side_effect=AssertionError('No unused curve')),patch('control_lap_pair.export_pair',side_effect=AssertionError('No comparison')):
  choose('A',3);choose('B',2);c['csv'].invoke();pump(.8)
 job=app.batch_job;assert not job.busy and job.states==['已完成','已完成'],job.errors
 assert [n for f,n in job.values]==[3,2] and job.names[0].startswith('A · ') and job.names[1].startswith('B · ')
 assert [v['number'] for _,v in sorted(job.results.items())]==[3,2]
 assert c['state']['result'] is None and not (folder/'SelectedLaps').exists() and not (app.data_path/'LapComparisons').exists()
 app.set_theme('light');app.toggle_language();pump(.2)
 assert c['csv'].enabled and c['csv'].winfo_rootx()+c['csv'].winfo_width()<=w.winfo_rootx()+w.winfo_width()+1
 assert c['csv'].winfo_rooty()+c['csv'].winfo_height()<=w.winfo_rooty()+w.winfo_height()+1
 choose('B',2);assert not c['csv'].enabled;choose('B',3);assert c['csv'].enabled
 with patch('control_evo_exports.filedialog.askdirectory') as pick:
  try:selected_csv(app,app.data_path.parent,[(folder,3)])
  except ValueError:pass
  else:raise AssertionError('Wrong root accepted')
  pick.assert_not_called()
 job.window.destroy();w.destroy();w=show(app,app.data_path);pump(.5);c=w.pair_controls
 assert c['state']['laps']['A'][c['numbers']['A'].get()]==2 and c['state']['laps']['B'][c['numbers']['B'].get()]==3
 w.destroy();assert not errors,errors;app.request_close();pump(.2)
print('EVO A/B CSV: nonfastest identities, snapshot roles, no extra analysis and retained UI choices OK')
'''
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            folder=record(Path(t)/'Simulators/ac_evo','valid');before={p:p.read_bytes() for p in (folder/'session.json',folder/'inputs.csv')}
            env=dict(os.environ,LMU_STINTRIX_DATA_DIR=t,STINTRIX_SIMULATOR='ac_evo',LMU_STINTRIX_HOTKEYS='0',PYTHONIOENCODING='utf-8')
            result=subprocess.run([sys.executable,'-c',script],cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',timeout=30)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            for p,body in before.items():self.assertEqual(p.read_bytes(),body)


if __name__=='__main__':unittest.main()
