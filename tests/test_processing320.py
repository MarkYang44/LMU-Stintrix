"""Bounded header batches, remembered lap identities and EVO best-lap shortcuts."""
import csv,io,json,math,os,shutil,subprocess,sys,tempfile,tracemalloc,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))


class Data(unittest.TestCase):
    def test_unselected_rows_batch_validation_is_bounded_and_preserves_headers(self):
        from json_store import Reader
        class Decoder(json.JSONDecoder):
            calls=0
            def raw_decode(self,*args,**kwargs):self.calls+=1;return super().raw_decode(*args,**kwargs)
        value=dict(meta=dict(name='赛道 🏁',zero=-0.0,big=2**80),data=[[i*.12345678901234567,None,-0.0] for i in range(12000)],tail=True)
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            path=Path(t)/'data.json';path.write_text(json.dumps(value,ensure_ascii=False),'utf-8')
            with path.open(encoding='utf-8') as stream:
                reader=Reader(stream,fields=('meta','tail'));reader.decoder=Decoder()
                tracemalloc.start()
                try:result=reader.value();reader.space();peak=tracemalloc.get_traced_memory()[1]
                finally:tracemalloc.stop()
            self.assertEqual(result,dict(meta=value['meta'],tail=True));self.assertFalse(reader.peek())
            self.assertLess(reader.decoder.calls,800);self.assertLess(peak,2_000_000)
            self.assertEqual(type(result['meta']['big']),int);self.assertLess(math.copysign(1,result['meta']['zero']),0)
            cases=[[[1,2],[None,-0.0],[1e-250,1e250]],[[1],[True,False]],[[1],['text ] "',None]],
                [[1],[{'nested':[2,3]}]],[[1],[float('nan'),float('inf')]],[[1],[2**90]]]
            for rows in cases:
                for chunk in (1,7,65536):
                    reader=Reader(io.StringIO(json.dumps(dict(data=rows,meta=value['meta']))),fields=('meta',),chunk_size=chunk)
                    self.assertEqual(reader.value(),{'meta':value['meta']});reader.space();self.assertFalse(reader.peek())

    def test_invalid_unselected_rows_and_native_integer_limits_are_not_hidden(self):
        from json_store import Reader
        bodies=['[[1,2],[3,]]','[[1],[01]]','[[1],[1e+]]','[[1],[.1]]','[[1],[truefalse]]',
            '[[1] [2]]','[[1],[2]],','[[1],[2]','[[1],["unterminated]]','[[1],{"x":}]']
        limit=getattr(sys,'get_int_max_str_digits',lambda:0)()
        if limit:bodies.append('[[1],['+'1'*(limit+1)+']]')
        for body in bodies:
            text='{"data":'+body+',"meta":1}'
            for chunk in (3,65536):
                with self.subTest(body=body[:25],chunk=chunk),self.assertRaises(ValueError):
                    reader=Reader(io.StringIO(text),fields=('meta',),chunk_size=chunk);reader.value();reader.space()
                    if reader.peek():raise ValueError('Trailing content')

    def test_legacy_analysis_headers_match_metadata_without_creating_sidecars(self):
        from analysis_headers import load
        value=dict(laps=[dict(number=i,time_s=100.12345678901234,conditions=dict(fuel_l=11.123456789),
            profile=[[j*.12345678901234567,None,-0.0] for j in range(1200)],action={'keep':'out'},vehicle_summary={'out':True}) for i in range(4)],
            recent_stability=dict(median=100.12345678901234),stable_reference_file='stable.lap.json')
        expected={**value,'laps':[{k:v for k,v in row.items() if k not in ('profile','action','vehicle_summary')} for row in value['laps']]}
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            folder=Path(t);path=folder/'session_analysis.json';path.write_text(json.dumps(value),'utf-8');before=path.read_bytes()
            self.assertEqual(load(folder),expected);self.assertEqual(path.read_bytes(),before)
            self.assertEqual({p.name for p in folder.iterdir()},{'session_analysis.json'})


@unittest.skipUnless(os.name=='nt','Native Windows Tk')
class UI(unittest.TestCase):
    from tests.test_ui_efficiency import EfficiencyTests as helpers
    app=helpers.app;pump=helpers.pump
    def test_lmu_reopen_restores_identities_last_page_and_revalidates_missing_laps(self):
        from control_lap_pair import show,remember_result
        from tests.test_ui_polish57 import records,LAPS
        with patch('control_center.SIMULATOR','lmu'):app,root,errors=self.app()
        self.assertEqual(app.simulator,'lmu');items=records(root);rows={Path(e['folder']).name:list(LAPS) for e in items}
        page=root/'last-comparison.html';page.write_text('private fixture','utf-8');remember_result(app,root,page)
        with patch('control_lap_pair.inventory',return_value=items),patch('control_lap_pair.valid_laps',side_effect=lambda f:rows[Path(f).name]),patch('control_lap_pair.finished_metadata',side_effect=lambda f:next(e for e in items if Path(e['folder'])==Path(f))):
            window=show(app,root,[e['folder'] for e in items[:2]]);self.pump(app,.5);c=window.pair_controls
            c['numbers']['A'].set(next(label for label,n in c['state']['laps']['A'].items() if n==2))
            c['quick']['swap'].invoke();c['query'].set('BMW');c['search'].flush();self.pump(app,.05)
            wanted={k:(c['state']['events'][c['events'][k].get()]['folder'],c['state']['laps'][k][c['numbers'][k].get()]) for k in ('A','B')}
            window.destroy();self.pump(app,.05)
            window=show(app,root,[e['folder'] for e in items[:2]]);self.pump(app,.5);c=window.pair_controls
            self.assertEqual(c['query'].get(),'BMW');self.assertTrue(c['reopen'].enabled)
            self.assertEqual(c['state']['result'],str(page))
            for key,(folder,number) in wanted.items():
                self.assertEqual(c['state']['events'][c['events'][key].get()]['folder'],folder)
                self.assertEqual(c['state']['laps'][key][c['numbers'][key].get()],number)
            app.set_theme('light');app.toggle_language();self.pump(app,.2);self.assertTrue(c['compare'].enabled)
            missing=next(k for k,(_,number) in wanted.items() if number==2);folder=wanted[missing][0]
            window.destroy();rows[Path(folder).name]=[v for v in LAPS if v['number']!=2]
            window=show(app,root);self.pump(app,.5);c=window.pair_controls
            self.assertEqual(c['numbers'][missing].get(),'');self.assertFalse(c['compare'].enabled)
            window.destroy();window=show(app,root,[items[2]['folder']]);self.pump(app,.4);c=window.pair_controls
            self.assertEqual(c['query'].get(),'');self.assertEqual(c['state']['events'][c['events']['A'].get()]['folder'],items[2]['folder']);window.destroy()
            window=show(app,root);self.pump(app,.3);c=window.pair_controls;c['choose_track']()
            label=next(label for label,e in c['state']['events'].items() if e['folder']==items[2]['folder'])
            c['events']['B'].set(label);c['scan']('B');self.pump(app,.3);window.destroy()
            window=show(app,root);self.pump(app,.4);c=window.pair_controls
            self.assertEqual(c['events']['A'].get(),'');self.assertEqual(c['state']['events'][c['events']['B'].get()]['folder'],items[2]['folder']);window.destroy()
        other=root/'Simulators/ac_evo'
        with patch('control_lap_pair.inventory',return_value=[]):
            window=show(app,other);self.pump(app,.3)
            self.assertEqual(window.pair_controls['query'].get(),'');self.assertIsNone(window.pair_controls['state']['result'])
            with self.assertRaises(ValueError):remember_result(app,other,page)
            window.destroy()
        self.assertFalse(errors)

    def test_evo_best_comparison_and_reopen_use_current_game_and_keep_source_bytes(self):
        script=r'''
import json,sys,time,traceback
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'src'))
from unittest.mock import patch
from control_center import ControlCenter
errors=[]
with patch.object(ControlCenter,'repair_windows_entry'):
 app=ControlCenter();assert app.simulator=='ac_evo';app.root.geometry('1200x850');app.root.report_callback_exception=lambda *a:errors.append(''.join(traceback.format_exception(*a)))
 def pump(seconds=.4):
  end=time.monotonic()+seconds
  while time.monotonic()<end:app.root.update();time.sleep(.005)
 app.show_page(1);pump(1);app.review_menu.invoke('all');pump(.1)
 action=next(a for a in app.review_menu.actions if a.key=='compare-best');assert action.visible() and action.enabled()
 with patch('control_center.os.startfile') as opened:
  app.review_menu.invoke('compare-best');pump(1)
  assert opened.call_count==1
  page=Path(opened.call_args.args[0]);assert page.is_file() and page.is_relative_to(app.data_path) and page.name.startswith('EVO_Compare_')
 app.selected_laps();pump(.7);window=app.lap_pair_window;c=window.pair_controls
 assert c['state']['result']==str(page) and c['reopen'].enabled
 c['numbers']['A'].set(next(label for label,n in c['state']['laps']['A'].items() if n==3));c['query'].set('Ferrari');c['search'].flush()
 window.destroy();app.selected_laps();pump(.7);c=app.lap_pair_window.pair_controls
 assert c['state']['laps']['A'][c['numbers']['A'].get()]==3 and c['query'].get()=='Ferrari'
 assert c['state']['result']==str(page) and c['compare'].enabled
 app.set_theme('light');pump(.2);app.toggle_language();pump(.2);assert c['compare'].enabled
 app.lap_pair_window.destroy();assert not errors,errors;app.request_close();pump(.2)
print('EVO one-click best laps, remembered selections, bilingual/theme context OK')
'''
        from tests.test_evo_records310 import fixture
        from evo_laps import export
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            game=Path(t)/'Simulators/ac_evo';a=fixture(game)
            with (a/'inputs.csv').open(encoding='utf-8',newline='') as stream:reader=csv.DictReader(stream);fields=reader.fieldnames;rows=list(reader)
            for row in rows:row['lap_invalidated']='0'
            with (a/'inputs.csv').open('w',encoding='utf-8',newline='') as stream:writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)
            b=game/'Logs/another';shutil.copytree(a,b)
            for folder in (a,b):export(folder)
            before={p:p.read_bytes() for f in (a,b) for p in (f/'session.json',f/'inputs.csv')}
            env=dict(os.environ,LMU_STINTRIX_DATA_DIR=t,STINTRIX_SIMULATOR='ac_evo',LMU_STINTRIX_HOTKEYS='0',PYTHONIOENCODING='utf-8')
            result=subprocess.run([sys.executable,'-c',script],cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',timeout=30)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            for path,value in before.items():self.assertEqual(path.read_bytes(),value)


if __name__=='__main__':unittest.main()
