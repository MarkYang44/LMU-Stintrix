"""Focused EVO facets, official layout assets, branding and safe delete wiring."""
import io,json,os,sys,tempfile,subprocess,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))


class Rules(unittest.TestCase):
    def test_brand_group_search_facets_and_official_layouts(self):
        from evo_art import catalog,resources
        from evo_gallery import matches
        cars=catalog()['cars'];self.assertEqual(len(cars),74)
        self.assertTrue(all(e.get('brand') and e.get('group') and e.get('category') for e in cars))
        selected=matches(cars,'296','Ferrari','gt3');self.assertEqual([e['name'] for e in selected],['Ferrari 296 GT3'])
        self.assertEqual(matches(cars,'296','Ferrari','road')[0]['name'],'Ferrari 296 GTB (2021)')
        self.assertFalse(matches(cars,'296','BMW','gt3'))
        tracks={e['name']:e for e in catalog()['tracks'] if not e.get('layouts')}
        self.assertEqual(len(tracks['Nurburgring']['configurations']),2)
        self.assertEqual(len(tracks['Watkins Glen']['configurations']),4)
        self.assertEqual(len(tracks['Paul Ricard']['configurations']),4)
        configs=[c for e in tracks.values() for c in e['configurations']]
        self.assertEqual(len(configs),36)
        maps=[c for c in configs if c.get('url')]
        self.assertEqual(len(maps),31);self.assertEqual(len({c['file'] for c in maps}),31)
        self.assertEqual([c['name'] for c in tracks['Brands Hatch']['configurations']],['GP','Indy'])
        self.assertEqual([c['name'] for c in tracks['Suzuka']['configurations']],['GP','East','West'])
        self.assertTrue(all(c['url'].startswith(('https://assettocorsa.gg/wp-content/uploads/','https://msvstatic.blob.core.windows.net/')) for c in maps))

    def test_static_svg_download_roundtrip_cache_and_theme_keep_shading(self):
        from evo_art import download,validate_svg
        from guide_cards import diagram_image
        from PIL import Image
        svg=b'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="40"><path fill="#fff" d="M0 0H40V40H0Z"/><path fill="#999" d="M50 0H90V40H50Z"/></svg>'
        entry=dict(name='Fixture',type='svg',url='https://assettocorsa.gg/wp-content/uploads/fixture.svg',file='fixture.png',raw_file='fixture.svg')
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t,patch('evo_art.catalog',return_value=dict(cars=[],tracks=[],branding=[entry],source='https://assettocorsa.gg/assetto-corsa-evo/')):
            with patch('urllib.request.urlopen',return_value=io.BytesIO(svg)) as network:
                self.assertEqual(download(t)['downloaded'],1);self.assertEqual(network.call_count,1)
            base=Path(t)/'assets/evo';self.assertEqual((base/'fixture.svg').read_bytes(),svg)
            with patch('urllib.request.urlopen',side_effect=AssertionError('Unnecessary download')):self.assertEqual(download(t)['errors'],[])
            with Image.open(base/'fixture.png') as image:
                dark=diagram_image(image,'#eeede8');light=diagram_image(image,'#262425')
                self.assertEqual(dark.getchannel('A').tobytes(),light.getchannel('A').tobytes())
                self.assertNotEqual(light.getpixel((100,100)),light.getpixel((600,100)))
        with self.assertRaises(ValueError):validate_svg(b'<svg xmlns="http://www.w3.org/2000/svg"><image href="file:///private"/></svg>')

    def test_report_logo_upgrade_is_local_backed_up_and_idempotent(self):
        from evo_art import refresh_branding
        from PIL import Image
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            root=Path(t)/'Simulators/ac_evo';assets=root/'assets/evo';assets.mkdir(parents=True)
            target=root/'RaceComRenderer';old=target/'Source/LMU Logo.png';old.parent.mkdir(parents=True)
            Image.new('RGBA',(20,10),'yellow').save(old);before=old.read_bytes()
            Image.new('RGBA',(100,40),'red').save(assets/'brand-evo-light.png')
            lmu=Path(t)/'RaceComRenderer/Source/LMU Logo.png';lmu.parent.mkdir(parents=True);lmu.write_bytes(b'original LMU')
            refresh_branding(root,target);self.assertEqual(old.read_bytes(),(assets/'brand-evo-light.png').read_bytes())
            self.assertEqual(next((target/'_stintrix_branding_history').glob('*.png')).read_bytes(),before)
            stamp=old.stat().st_mtime_ns;refresh_branding(root,target);self.assertEqual(old.stat().st_mtime_ns,stamp)
            self.assertEqual(lmu.read_bytes(),b'original LMU')


class UI(unittest.TestCase):
    def test_personal_record_source_delete_confirms_and_refreshes_without_a_review_selection(self):
        script=r'''
import sys,time,ctypes,traceback
from pathlib import Path
sys.path[:0]=[str(Path.cwd()/'src'),str(Path.cwd())]
ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
from unittest.mock import patch
from control_center import ControlCenter
from control_delete import remove_source
errors=[]
with patch.object(ControlCenter,'repair_windows_entry'):
 app=ControlCenter();app.root.report_callback_exception=lambda *a:errors.append(''.join(traceback.format_exception(*a)))
 def pump(s=.4):
  end=time.monotonic()+s
  while time.monotonic()<end:app.root.update();time.sleep(.005)
 app.show_page(6);pump(1);page=app.record_loaders['best'].page
 assert app.tree is None and len(page.rows)==1
 folder=Path(page.selected['folder'])
 with patch('control_danger.confirm',return_value=False) as ask:
  page.menu.invoke('delete-source');pump();assert ask.call_count==1
 assert folder.is_dir() and len(page.rows)==1
 with patch('control_danger.confirm',return_value=True):
  page.menu.invoke('delete-source');pump(1.2)
 assert not folder.exists() and not page.rows
 with patch('control_danger.confirm',side_effect=AssertionError('Foreign game was offered for deletion')):
  try:remove_source(app,dict(folder=str(app.data_path/'Logs/foreign'),session=dict(simulator_id='lmu')))
  except ValueError:pass
  else:raise AssertionError('Foreign game accepted')
 assert not errors,errors
 app.request_close();pump(.1)
print('Personal-record source deletion OK')
'''
        from tests.test_evo_records310 import fixture
        from evo_laps import export
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            folder=fixture(Path(t)/'Simulators/ac_evo');export(folder)
            env=dict(os.environ,LMU_STINTRIX_DATA_DIR=t,STINTRIX_SIMULATOR='ac_evo',LMU_STINTRIX_HOTKEYS='0',PYTHONIOENCODING='utf-8')
            child=subprocess.run([sys.executable,'-c',script],cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',timeout=30)
            self.assertEqual(child.returncode,0,child.stdout+child.stderr)

    def test_facets_layout_navigation_and_confirmed_delete_stay_in_evo(self):
        script=r'''
import sys,time,traceback,ctypes,json
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'src'))
ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
from unittest.mock import patch
from control_center import ControlCenter
from evo_art import catalog
from PIL import Image
errors=[]
with patch.object(ControlCenter,'repair_windows_entry'):
 app=ControlCenter();app.root.report_callback_exception=lambda *a:errors.append(''.join(traceback.format_exception(*a)))
 def pump(s=.4):
  end=time.monotonic()+s
  while time.monotonic()<end:app.root.update();time.sleep(.005)
 app.show_page(5);pump();g=app.evo_gallery
 g.variables['brand'].set('Ferrari');g.variables['group'].set('gt3');g.variables['query'].set('296');g.filter_changed();pump()
 assert [e['name'] for e in g.visible_entries]==['Ferrari 296 GT3']
 app.show_page(4);pump();g=app.evo_gallery
 g.variables['query'].set('Nurburgring');g.filter_changed();pump()
 i=next(i for i,e in enumerate(g.visible_entries) if e['name']=='Nurburgring')
 configs=g.visible_entries[i]['configurations'];assets=app.data_path/'assets/evo';assets.mkdir(parents=True,exist_ok=True)
 for c in configs:Image.new('RGBA',(100,80),'white').save(assets/c['file'])
 g.cards[i].event_generate('<Button-1>',x=3,y=3);pump()
 assert len(g.map_buttons)==2
 g.map_buttons['Nurburgring Sprint'].invoke();pump();assert g.selected_layout['name']=='Nurburgring Sprint'
 assert g.map_picture is not None
 app.set_theme('light');pump();assert app.evo_gallery.selected_layout['name']=='Nurburgring Sprint'
 assert app.evo_gallery.map_picture.image.getpixel((1,1))[0]<50,'Light theme retained white diagram ink'
 app.toggle_language();pump();app.evo_gallery.back();pump();assert app.evo_gallery.variables['query'].get()=='Nurburgring'
 app.show_page(5);pump();g=app.evo_gallery
 assert g.variables['brand'].get()=='Ferrari' and g.variables['group'].get()=='gt3'
 app.show_page(1);pump(.8);app.tree.selection_set(());app.update_toolbar();assert not app.review_actions['delete'].enabled
 targets=tuple(str(i) for i,e in enumerate(app.items) if e['track']!='Keep')
 app.tree.selection_set(targets);app.update_toolbar();assert app.review_actions['delete'].enabled
 with patch('control_danger.confirm',return_value=False) as ask:
  app.review_actions['delete'].invoke();pump();assert ask.call_count==1
 assert (app.data_path/'Logs/one/inputs.csv').read_bytes()==b'keep raw bytes'
 with patch('control_danger.confirm',return_value=True):
  app.review_actions['delete'].invoke();pump(1.2)
 assert not (app.data_path/'Logs/one').exists() and not (app.data_path/'Logs/two').exists()
 assert (app.data_path/'Logs/keep/session.json').exists()
 assert (app.data_path.parent.parent/'Logs/lmu/session.json').exists()
 assert not errors,errors
 app.request_close();pump(.1)
print('EVO facets, maps, persistence and isolated deletion OK')
'''
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            base=Path(t);evo=base/'Simulators/ac_evo'
            for name,track,game in [('one','Nurburgring','ac_evo'),('two','Nurburgring','ac_evo'),('keep','Keep','ac_evo'),('lmu','LMU','lmu')]:
                folder=(evo if game=='ac_evo' else base)/'Logs'/name;folder.mkdir(parents=True)
                (folder/'session.json').write_text(json.dumps(dict(simulator_id=game,track=track,vehicle='Ferrari 296 GTB',session=5,status='complete',started_utc='2026-10-27T10:00:00Z')),'utf-8')
                (folder/'inputs.csv').write_bytes(b'keep raw bytes')
            env=dict(os.environ,LMU_STINTRIX_DATA_DIR=t,STINTRIX_SIMULATOR='ac_evo',LMU_STINTRIX_HOTKEYS='0',PYTHONIOENCODING='utf-8')
            child=subprocess.run([sys.executable,'-c',script],cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',timeout=40)
            self.assertEqual(child.returncode,0,child.stdout+child.stderr)

if __name__=='__main__':unittest.main()
