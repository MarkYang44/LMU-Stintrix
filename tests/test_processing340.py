"""Exact review bytes and explicit cleanup of mixed EVO lap selections."""
import csv,os,struct,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT)]


def original(rows):
    pack=struct.Struct('<13d')
    return b''.join(pack.pack(*[float(v or (0 if i<10 else 'nan')) for i,v in enumerate(row)]) for row in rows)


class Data(unittest.TestCase):
    def test_review_bytes_sparse_nonfinite_signed_zero_precision_and_bounded_consumption(self):
        from reporting import review_records
        tokens=['1.2345678901234567','-0.0','1e-300','1e300','NaN','inf','-inf','\u0661.\u0665',0,False,'',None]
        rows=[['.12345678901234567']*13 for _ in range(640)]
        rows.extend([[token]*13 for token in tokens])
        for i in range(13):row=['1.2345678901234567']*13;row[i]='';rows.append(row)
        consumed=[];closed=[]
        def values(*a):
            try:
                for row in rows:consumed.append(1);yield row
            finally:closed.append(True)
        with patch('column_store.values',values):
            stream=review_records('unused');chunk=next(stream)
            self.assertLessEqual(len(consumed),631);self.assertLessEqual(len(chunk),65536+103)
            stream.close();self.assertEqual(closed,[True])
            chunks=list(review_records('unused'));self.assertEqual(b''.join(chunks),original(rows))
            self.assertTrue(all(len(c)<=65536+103 for c in chunks));self.assertEqual(len(b''.join(chunks)),len(rows)*104)
        for bad in ('invalid',' ',object()):
            with patch('column_store.values',return_value=iter([[bad]*13])):
                with self.assertRaises((ValueError,TypeError)):list(review_records('unused'))

    def test_plain_and_packed_review_match_original_and_failure_preserves_old_page(self):
        from reporting import review_records,REVIEW_COLUMNS,write_page
        from column_store import convert
        rows=[['1.2345678901234567','3','1234.1234567890123','.75','0','-.12345678901234567','.7','0','-.1','187.23456789012345','-0.0','12.345678901234567','5781'] for _ in range(700)]
        rows[6][10]='';rows[9][3]='';rows[13][11]='nan';rows[17][12]=''
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            folder=Path(t);path=folder/'inputs.csv';(folder/'session.json').write_text('{"status":"complete"}','utf-8')
            with path.open('w',encoding='utf-8-sig',newline='') as out:w=csv.writer(out);w.writerow(REVIEW_COLUMNS);w.writerows(rows)
            before=path.read_bytes();expected=original(rows);self.assertEqual(b''.join(review_records(path)),expected)
            convert(path);packed=folder/'inputs.csv.stc';packed_before=packed.read_bytes();self.assertEqual(path.read_bytes(),before)
            path.rename(folder/'original.csv');self.assertEqual(b''.join(review_records(path)),expected);self.assertEqual(packed.read_bytes(),packed_before)
            page=folder/'review.html';page.write_bytes(b'previous completed report')
            with patch('column_store.values',return_value=iter(rows+[['invalid']*13])):
                with self.assertRaises(ValueError):write_page(page,'<html>/*STINTRIX_BLOCKS*/</html>',[('inputs',review_records(path))])
            self.assertEqual(page.read_bytes(),b'previous completed report');self.assertFalse(list(folder.glob('*.pending')))


@unittest.skipUnless(os.name=='nt','Native Windows Tk')
class UI(unittest.TestCase):
    def test_keep_selected_usable_laps_preserves_context_and_never_substitutes_or_starts_work(self):
        script=r'''
import sys,time,traceback
from pathlib import Path
sys.path[:0]=[str(Path.cwd()/'src'),str(Path.cwd())]
from unittest.mock import patch
from control_center import ControlCenter
from control_evo_lap_overview import show
errors=[]
with patch.object(ControlCenter,'repair_windows_entry'):
 app=ControlCenter();app.root.withdraw();app.root.report_callback_exception=lambda *a:errors.append(''.join(traceback.format_exception(*a)))
 def pump(s=.15):
  end=time.monotonic()+s
  while time.monotonic()<end:app.root.update();time.sleep(.005)
 w=show(app,app.data_path/'Logs/evo');w.geometry('1000x820');pump(.7);c=w.lap_overview;table=c['table'];state=c['state'];button=c['buttons']['keep-usable']
 assert not button.winfo_manager() and not button.enabled
 with patch('evo_laps.index',side_effect=AssertionError('No index read')),patch('lap_scan_index.raw_rows',side_effect=AssertionError('No telemetry scan')),patch.object(app,'run_background',side_effect=AssertionError('Selection must not start work')):
  table.selection_set(('1','2','3','5'));pump();assert button.enabled and button.winfo_ismapped() and not c['buttons']['compare'].enabled
  c['sort']('time',True);table.scroller.move(table.limit());pump();order=tuple(table.order);offset=table.offset;before=table.selection();wanted=tuple(k for k in before if state['rows'][k]['usable'])
  state['loading']=True;table.viewport.event_generate('<<TreeviewSelect>>');pump();assert not button.enabled;button.action();assert table.selection()==before
  state['loading']=False;table.viewport.event_generate('<<TreeviewSelect>>');pump();button.invoke();pump()
  assert table.selection()==wanted and tuple(table.order)==order and table.offset==min(offset,table.limit()),(table.selection(),wanted,table.offset,offset,table.limit())
  assert c['buttons']['compare'].enabled and c['buttons']['csv'].enabled and not button.winfo_manager() and '取消选中 2' in c['status'].get()
  assert state['selection_summary']['total']==state['selection_summary']['valid']==2
  table.selection_set(('3','5'));pump();assert not button.winfo_manager();button.action();assert table.selection()==('3','5') or set(table.selection())=={'3','5'}
  table.selection_set(('1','3'));pump();c['rhythm'].toggle();pump();assert c['rhythm'].visible
  app.set_theme('light');app.toggle_language();pump(.25);assert button.enabled and button.cget('text')=='Keep selected usable laps'
  w.geometry('800x600');pump(.2)
  assert button.winfo_width()>=button.font.measure(button.cget('text'))
  assert max(b.winfo_rooty()+b.winfo_height() for b in c['buttons'].values() if b.winfo_ismapped())<=w.winfo_rooty()+w.winfo_height()+1
  button.invoke();pump();assert table.selection()==('1',) and c['rhythm'].visible and c['buttons']['curve'].enabled and not c['buttons']['compare'].enabled
  c['rhythm'].toggle();pump();c['kind'].set('other');c['populate']();pump();assert not button.winfo_manager() and not table.selection()
 # A failed refresh clears the contextual control and stale selection.
 with patch('evo_lap_overview.load',side_effect=OSError('Refresh failed')):c['refresh']();pump(.35)
 assert state['result'] is None and not button.winfo_manager() and not button.enabled
 w.destroy();assert not errors,errors;app.request_close();pump(.15)
'''
        from tests.test_processing329 import fixture
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            folder=fixture(Path(t)/'Simulators/ac_evo',laps=16);path=folder/'inputs.csv'
            with path.open(encoding='utf-8',newline='') as stream:r=csv.DictReader(stream);fields=r.fieldnames;rows=list(r)
            for row in rows:
                if row['lap']=='4':row['lap_invalidated']='1'
                if row['lap']=='6':row['lap_invalidated']=''
            with path.open('w',encoding='utf-8',newline='') as stream:w=csv.DictWriter(stream,fieldnames=fields);w.writeheader();w.writerows(rows)
            before={p:p.read_bytes() for p in (path,folder/'session.json')}
            env=dict(os.environ,LMU_STINTRIX_DATA_DIR=t,STINTRIX_SIMULATOR='ac_evo',LMU_STINTRIX_HOTKEYS='0',PYTHONIOENCODING='utf-8')
            result=subprocess.run([sys.executable,'-c',script],cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',timeout=35,creationflags=0x08000000)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            for p,data in before.items():self.assertEqual(p.read_bytes(),data)
