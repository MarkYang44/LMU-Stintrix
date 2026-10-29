"""Bounded legacy headers and EVO comparison choices without extra telemetry."""
import json,math,os,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))


class Data(unittest.TestCase):
    def test_headers_reuse_isolated_values_and_revalidate_source_and_sidecar(self):
        import analysis_headers as h
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            folder=Path(t);path=folder/'session_analysis.json'
            value=dict(laps=[dict(number=1,time_s=100.12345678901234,zero=-0.,conditions={'fuel':None},profile=[[i,None,-0.] for i in range(300)])],recent_stability={'median':2**80},stable_reference_file='圈.json')
            path.write_text(json.dumps(value,ensure_ascii=False),'utf-8');before=path.read_bytes()
            h._cache.clear();expected=h._read(path);first=h.load(folder)
            self.assertEqual(first,expected);first['laps'][0]['conditions']['fuel']=99
            with patch.object(h,'_read',side_effect=AssertionError('Duplicate legacy scan')):
                result=h.load(folder)
            self.assertEqual(result,expected);self.assertLess(math.copysign(1,result['laps'][0]['zero']),0)
            self.assertEqual(path.read_bytes(),before);self.assertFalse((folder/'analysis_index.json').exists())
            value['laps'][0]['time_s']=101.12345678901234;path.write_text(json.dumps(value),'utf-8')
            self.assertEqual(h.load(folder)['laps'][0]['time_s'],value['laps'][0]['time_s'])
            indexed=dict(laps=[{'number':9,'time_s':90.12345678901234}],recent_stability={},stable_reference_file=None)
            h.save(folder,indexed);self.assertEqual(h.load(folder),indexed)
            side=folder/'analysis_index.json';old=side.read_bytes();side.unlink();self.assertEqual(h.load(folder)['laps'][0]['number'],1)
            side.write_bytes(old);self.assertEqual(h.load(folder),indexed)
            path.write_text('{"laps":[}',encoding='utf-8')
            for _ in range(2):
                with self.assertRaises(ValueError):h.load(folder)
            path.unlink();self.assertEqual(h.load(folder),{})

    def test_headers_bound_retention_and_reject_a_changed_read_without_publishing(self):
        import analysis_headers as h
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            root=Path(t);h._cache.clear()
            for i in range(6):
                folder=root/str(i);folder.mkdir();(folder/'session_analysis.json').write_text('{"laps":[]}',encoding='utf-8');h.load(folder)
            self.assertLessEqual(len(h._cache),4);self.assertLessEqual(sum(map(len,h._cache.values())),4*256*1024)
            self.assertIsNone(h._payload({'laps':[{'note':'x'*(h._MAX_BYTES+1)}]}))
            self.assertIsNone(h._payload({'points':object()}))
            folder=root/'large';folder.mkdir();path=folder/'session_analysis.json';path.write_text(json.dumps({'laps':[{'note':'x'*(h._MAX_BYTES+1)}]}),'utf-8')
            h._cache.clear();self.assertEqual(len(h.load(folder)['laps'][0]['note']),h._MAX_BYTES+1);self.assertFalse(h._cache)
            original=h._read
            def changed(source):
                result=original(source);path.write_text('{"laps":[]}',encoding='utf-8');return result
            with patch.object(h,'_read',side_effect=changed),self.assertRaises(OSError):h.load(folder)
            self.assertFalse(h._cache);self.assertEqual(h.load(folder),{'laps':[]})


@unittest.skipUnless(os.name=='nt','Native Windows Tk')
class UI(unittest.TestCase):
    def test_evo_comparison_cross_filter_context_keyboard_and_bilingual_layout(self):
        script=r'''
import sys,time,traceback,ctypes
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'src'))
ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
from unittest.mock import patch
from control_center import ControlCenter
from evo_art import catalog
from PIL import Image
errors=[]
with patch.object(ControlCenter,'repair_windows_entry'),patch('evo_art.download',side_effect=AssertionError('No automatic network')),patch('evo_laps.index',side_effect=AssertionError('Gallery must not scan telemetry')):
 app=ControlCenter();app.root.geometry('1450x1000+20+20');app.root.report_callback_exception=lambda *a:errors.append(''.join(traceback.format_exception(*a)))
 def pump(s=.3):
  end=time.monotonic()+s
  while time.monotonic()<end:app.root.update();time.sleep(.005)
 assets=app.data_path/'assets/evo';assets.mkdir(parents=True,exist_ok=True)
 names=['Abarth 695 Biposto (2022)','Alfa Romeo 75 1.8 Turbo Evoluzione (1987)']
 for entry in catalog()['cars']:
  if entry['name'] in names:Image.new('RGB',(108,60),'yellow').save(assets/entry['file'])
 app.show_page(5);pump(.5);g=app.evo_gallery;assert not g.compare_button.enabled
 original=[str(w) for w in g.host.winfo_children()]
 g.car_buttons[names[0]].invoke();assert [str(w) for w in g.host.winfo_children()]==original
 g.variables['brand'].set('Alfa Romeo');pump(.2);g.car_buttons[names[1]].invoke();pump(.15)
 assert g.state['comparison']==names and g.compare_button.enabled
 assert all(b.enabled==(n in names) for n,b in g.car_buttons.items())
 g.select_car('foreign LMU');assert g.state['comparison']==names
 app.scroll.yview_moveto(.2);pump(.1);fraction=app.scroll.yview()[0]
 g.compare_button.invoke();pump(.8);assert g.state['mode']=='compare' and g.comparison.cells[0].grid_info()['row']==0
 from guide_cards import Picture
 pictures=[w for cell in g.comparison.cells for w in cell.winfo_children() if isinstance(w,Picture)]
 assert len(pictures)==2 and all(p.photo is not None for p in pictures)
 g.back();pump(.3);assert abs(app.scroll.yview()[0]-fraction)<.03 and g.variables['brand'].get()=='Alfa Romeo',(fraction,app.scroll.yview(),g.state,g.browse.winfo_height(),app.scroll.cget('scrollregion'))
 assert all(p.photo is None for p in pictures)
 g.compare_button.invoke();pump(.2);app.root.minsize(800,650);app.root.geometry('900x760');pump(.3)
 assert g.comparison.cells[1].grid_info()['row']==1,(app.root.geometry(),g.comparison.winfo_width(),g.comparison.cells[1].grid_info())
 for cell in g.comparison.cells:assert cell.winfo_width()<=g.comparison.winfo_width()+1
 app.set_theme('light');app.toggle_language();app.root.minsize(800,650);app.root.geometry('900x760');pump(.6);g=app.evo_gallery
 assert g.state['comparison']==names and g.state['mode']=='compare'
 assert g.comparison.cells[1].grid_info()['row']==1
 app.focus_search();pump(.2);assert g.state['mode']=='browse' and app.root.focus_get() is g.search.entry
 assert g.variables['brand'].get()=='Alfa Romeo' and g.state['comparison']==names
 g.selection_chips.buttons[names[0]].invoke();pump(.1);assert g.state['comparison']==names[1:] and not g.compare_button.enabled
 g.select_car(names[0]);g.compare_button.invoke();pump(.1)
 app.show_page(4);pump(.2);app.show_page(5);pump(.4);g=app.evo_gallery
 assert g.state['mode']=='compare' and g.state['comparison']==names[::-1]
 g.back();g.clear_button.invoke();pump(.2);assert not g.state['comparison'] and not g.compare_button.enabled
 assert not errors,errors;app.request_close();pump(.1)
print('EVO compare: exact catalogue, filter/page retention, released images, keyboard, light/English and narrow layout OK')
'''
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            env=dict(os.environ,LMU_STINTRIX_DATA_DIR=t,STINTRIX_SIMULATOR='ac_evo',LMU_STINTRIX_HOTKEYS='0',PYTHONIOENCODING='utf-8')
            result=subprocess.run([sys.executable,'-c',script],cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',timeout=35)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)


if __name__=='__main__':unittest.main()
