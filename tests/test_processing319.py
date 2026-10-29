"""Single-pass EVO exports, bounded JSON tokens and game-scoped workflow reuse."""
import csv,io,json,math,os,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from tests.test_evo_records310 import fixture
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))


class Data(unittest.TestCase):
    def test_json_tokens_flat_headers_preserve_types_and_stream_matrices(self):
        import json_store
        from analysis_spool import DiskTable
        from tests.test_lossless_storage import plain
        value=dict(text='赛车 "\\\n\u0000 🏁',tags=['race',None,True,2**90,-0.0],
            data=[[.12345678901234567,None,-0.0,1.234e-250],[1e250,2.,None,3.]],tail=False)
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            for chunk in (1,2,11,65536):
                reader=json_store.Reader(io.StringIO(' '*701+json.dumps(value,ensure_ascii=False)+'\r\n'),t,chunk)
                loaded=reader.value();reader.space();self.assertFalse(reader.peek())
                self.assertIsInstance(loaded['data'],DiskTable)
                self.assertEqual(plain(loaded),value);self.assertLess(math.copysign(1,loaded['data'][0][2]),0)
                loaded['data'].close()
            path=Path(t)/'tags.json';header=dict(tags=value['tags'],options=dict(names=['a','b']),count=2**90)
            path.write_text(json.dumps(header),'utf-8')
            with patch('paths.data_directory',side_effect=AssertionError('Flat metadata must not create scratch data')):
                loaded=json_store.load(path);self.assertEqual(loaded,header)
                self.assertIs(type(loaded['tags'][2]),bool);self.assertIs(type(loaded['count']),int)
                self.assertEqual(json_store.load(path,fields=('tags',)),{'tags':value['tags']})
            for text in ('{\n"x":1e+}', '{"x":truefalse}', '{"x":1}\v', '{"x":"escape\\"}', '{"data":[[1,2],]}'):
                for chunk in (1,7):
                    with self.assertRaises(ValueError):
                        reader=json_store.Reader(io.StringIO(text),t,chunk);reader.value();reader.space()
                        if reader.peek():raise ValueError('Trailing JSON')

    def test_evo_curve_csv_share_one_range_and_failed_exports_keep_previous_files(self):
        from evo_laps import index
        from evo_comparison import selected
        from lap_scan_index import raw_rows
        from column_store import convert
        for packed in (False,True):
            with self.subTest(packed=packed),tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
                folder=fixture(Path(t)/'Simulators/ac_evo');source=folder/'inputs.csv'
                with source.open(newline='',encoding='utf-8') as stream:reader=csv.DictReader(stream);fields=reader.fieldnames;rows=list(reader)
                rows[130]['utc']='quoted, "UTC"\r\nnext line'
                fields=[*fields,'extra','extra','throttle']
                with source.open('w',newline='',encoding='utf-8') as stream:
                    writer=csv.writer(stream);writer.writerow(fields)
                    for row in rows:writer.writerow([*(row.get(k,'') for k in fields[:-3]),'first','last','.9876543210987654'])
                with source.open(newline='',encoding='utf-8') as stream:expected=list(csv.DictReader(stream))[100:200]
                original=source.read_bytes()
                if packed:convert(source,replace=True)
                inventory=index(folder);meta=json.loads((folder/'session.json').read_text('utf-8'))
                with patch('lap_scan_index.raw_rows',wraps=raw_rows) as reads:item,record=selected(folder,2,inventory,meta)
                self.assertEqual(reads.call_count,1);self.assertEqual(len(record['data']),100)
                self.assertEqual(record['data'][0][2],.9876543210987654);record['data'].close()
                with Path(item['csv']).open(newline='',encoding='utf-8') as stream:self.assertEqual(list(csv.DictReader(stream)),expected)
                before={key:Path(item[key]).read_bytes() for key in ('json','csv')}
                with patch('lap_exports.cached',return_value=None),patch('evo_laps.stamp',return_value={'changed':True}):
                    with self.assertRaises(OSError):selected(folder,2,inventory,meta)
                self.assertFalse(list((folder/'SelectedLaps').glob('*.pending')))
                for key,value in before.items():self.assertEqual(Path(item[key]).read_bytes(),value)
                from telemetry_file import Path as ReadPath
                self.assertEqual(ReadPath(source).read_bytes(),original)

    def test_evo_participation_batch_isolated_and_original_evidence_unchanged(self):
        from race_mode_overrides import save,load
        from library import inventory
        from evo_control import open_directory
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            root=Path(t)/'Simulators/ac_evo';a=fixture(root);b=root/'Logs/known';shutil.copytree(a,b)
            meta=json.loads((b/'session.json').read_text('utf-8'));meta['race_mode']='single';(b/'session.json').write_text(json.dumps(meta),'utf-8')
            original={p:p.read_bytes() for f in (a,b) for p in (f/'session.json',f/'inputs.csv')}
            self.assertEqual(save(root,[a,b],'online',only_unknown=True),1)
            self.assertEqual({v['race_mode'] for v in inventory(root)},{'online','single'})
            receipt=root/'RaceModes/overrides.json';before=receipt.read_bytes()
            foreign=root/'Logs/foreign';shutil.copytree(a,foreign)
            meta.pop('simulator_id');(foreign/'session.json').write_text(json.dumps(meta),'utf-8')
            with self.assertRaises(ValueError):save(root,[a,foreign],'single')
            self.assertEqual(receipt.read_bytes(),before);self.assertEqual(load(root)['entries']['Logs/evo']['race_mode'],'online')
            app=SimpleNamespace(data_path=root)
            with patch('os.startfile') as opened:
                open_directory(app,dict(folder=str(a)));opened.assert_called_once_with(str(a.resolve()))
                with self.assertRaises(ValueError):open_directory(app,dict(folder=str(foreign)))
            for path,value in original.items():self.assertEqual(path.read_bytes(),value)


class UI(unittest.TestCase):
    def test_evo_menu_batch_correction_folder_and_context_survive_theme_language(self):
        script=r'''
import json,os,sys,time,traceback
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
 app.show_page(1);pump(1)
 actions={a.key:a for a in app.review_menu.actions}
 assert {'mode','folder','all','clear'}<=set(actions)
 assert not actions['mode'].enabled() and not actions['folder'].enabled()
 app.search.set('Nurburgring');app.populate();app.review_menu.invoke('all');pump(.1)
 before={app.items[int(i)]['folder'] for i in app.tree.selection()};assert len(before)==2
 app.review_menu.open();pump(.05)
 assert 'mode' in app.review_menu.positions and 'folder' not in app.review_menu.positions and 'note' not in app.review_menu.positions
 groups=[a.group for a in app.review_menu.actions if a.visible()]
 changes=[g for i,g in enumerate(groups) if i==0 or g!=groups[i-1]];assert len(changes)==len(set(changes))
 app.review_menu.close()
 app.review_menu.invoke('mode');pump(.1);editor=app.participation_editor
 assert editor.mode_controls['only_unknown'].get()
 editor.mode_controls['choice'].set('online');assert editor.mode_controls['save']();pump(.8)
 assert app.search.get()=='Nurburgring' and {app.items[int(i)]['folder'] for i in app.tree.selection()}==before
 assert {e['race_mode'] for e in app.items}=={'online','single'}
 app.tree.selection_set((app.tree.get_children()[0],));pump(.1)
 assert actions['folder'].visible() and actions['note'].visible()
 with patch('os.startfile') as opened:
  app.review_menu.invoke('folder');opened.assert_called_once()
  assert Path(opened.call_args.args[0]).is_relative_to(app.data_path)
 app.set_theme('light');pump(.3);app.toggle_language();pump(.5)
 assert app.search.get()=='Nurburgring' and len(app.tree.selection())==1
 app.review_menu.invoke('clear');pump(.05);assert not app.tree.selection()
 assert not errors,errors
 app.request_close();pump(.2)
print('EVO batch correction, folder action and retained browsing context OK')
'''
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            root=Path(t)/'Simulators/ac_evo';a=fixture(root);b=root/'Logs/known';shutil.copytree(a,b)
            path=b/'session.json';meta=json.loads(path.read_text('utf-8'));meta['race_mode']='single';path.write_text(json.dumps(meta),'utf-8')
            originals={p:p.read_bytes() for f in (a,b) for p in (f/'session.json',f/'inputs.csv')}
            env=dict(os.environ,LMU_STINTRIX_DATA_DIR=t,STINTRIX_SIMULATOR='ac_evo',LMU_STINTRIX_HOTKEYS='0',PYTHONIOENCODING='utf-8')
            result=subprocess.run([sys.executable,'-c',script],cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',timeout=30)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            for path,value in originals.items():self.assertEqual(path.read_bytes(),value)


if __name__=='__main__':unittest.main()
