"""EVO details show observed facts, retain real zeros, and preserve navigation."""
import copy,json,os,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))


def entry(root,track='Monza'):
    from tests.test_record_intelligence import entry as base
    value=base(111.255,group='Unknown · Ferrari 296 GT3');folder=Path(root)/'Logs'/track;folder.mkdir(parents=True,exist_ok=True)
    file=folder/'fastest_lap.json';file.write_text('{"original":"keep"}','utf-8')
    value.update(track=track,file=str(file),folder=str(folder),identity=(track,'GP',5000,'ac_evo','Ferrari 296 GT3'))
    value['session'].update(simulator_id='ac_evo',track=track,vehicle='Ferrari 296 GT3',session=5,race_mode='single')
    value['lap'].update(sample_count=13350,timing_source='evo_last_laptime_ms')
    return value


class Data(unittest.TestCase):
    def test_unknowns_duplicates_and_missing_sections_are_hidden_without_changing_identity(self):
        from record_presentation import present
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as temp:
            value=entry(temp);before=copy.deepcopy(value);result=present(value,dict(conditions={}))
            self.assertEqual(result['car'],'Ferrari 296 GT3');self.assertEqual(set(result['facts']),{'layout','samples','timing'})
            self.assertNotIn('未知',str(result));self.assertNotIn('Unknown',str(result));self.assertEqual(value,before)
            value['vehicle_class']=value['session']['vehicle'];self.assertEqual(present(value,{})['car'],value['session']['vehicle'])
            value['session'].update(vehicle_class='GT3',started_utc='bad',session=None)
            self.assertEqual(present(value,{})['car'],'GT3 · Ferrari 296 GT3');self.assertNotIn('未知',present(value,{})['context'])

    def test_actual_zero_values_survive_and_missing_or_nonfinite_values_never_make_tiles(self):
        from record_presentation import present
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as temp:
            value=entry(temp);detail=dict(conditions=dict(fuel_l=0.,track_temp_c=0.,ambient_temp_c=float('nan'),wetness=0.,rain=0.,tyre_front_name='Unknown',tyre_compound=0,tc_level=0,abs_level=None),vehicle_summary=dict(fl_wear_fraction=dict(start=0.)))
            result=present(value,detail)['facts'];self.assertEqual(result['fuel'],'0.0 L');self.assertEqual(result['track_temp'],'0.0 °C')
            self.assertEqual(result['wetness'],'干燥');self.assertEqual(result['rain'],'无雨');self.assertEqual(result['front'],'胎种编号 0')
            self.assertEqual(result['remaining'],'0.0 %');self.assertEqual(result['assists'],'TC 0');self.assertNotIn('air_temp',result);self.assertNotIn('rear',result)
            self.assertNotIn('未知',str(result));self.assertNotIn('ABS',result['assists'])


@unittest.skipUnless(os.name=='nt','Native Tk')
class UI(unittest.TestCase):
    def pump(self,app,seconds=.2):
        end=time.monotonic()+seconds
        while time.monotonic()<end:app.root.update();time.sleep(.004)

    def test_evo_sparse_facts_balanced_photos_navigation_themes_and_disposal(self):
        from control_center import ControlCenter
        from PIL import Image
        from control_widgets import px
        import tkinter as tk
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as temp:
            root=Path(temp)/'Simulators/ac_evo';root.mkdir(parents=True);values=[entry(root),entry(root,'Silverstone')]
            for n in ('car.jpg','track.jpg'):
                p=root/'assets/evo'/n;p.parent.mkdir(parents=True,exist_ok=True);Image.new('RGB',(160,90),'#555555').save(p)
            def image(kind,name,layout='',root=None):
                if name=='Silverstone':return None
                return dict(local_image=str(root/'assets/evo'/('car.jpg' if kind=='cars' else 'track.jpg')))
            def detail(e):return dict(conditions={},curve=[(0,[0.,0.],[.5,.2]),(599,[1.,0.],[1.,1.])])
            before={p:p.read_bytes() for p in root.rglob('*') if p.is_file()}
            with patch('control_center.ROOT',root),patch('control_center.SIMULATOR','ac_evo'),patch.object(ControlCenter,'repair_windows_entry'),patch('control_best.read_records',return_value=values),patch('control_best.read_detail',side_effect=detail),patch('evo_art.item',side_effect=image):
                app=ControlCenter();errors=[];app.root.report_callback_exception=lambda *a:errors.append(a);app.root.maxsize(4096,4096);app.root.geometry('1440x1000')
                try:
                    app.show_page(6);self.pump(app,.4);page=app.record_loaders['best'].page
                    chosen=next(key for key,e in page.lookup.items() if e['track']=='Monza');page.table.selection_set((chosen,));self.pump(app)
                    self.assertEqual(set(page.evo_facts.visible),{'layout','samples','timing'});self.assertEqual(page.car_label.cget('text'),'Ferrari 296 GT3')
                    self.assertEqual(page.header.columns,2);self.assertLessEqual(abs(page.header.images[0].winfo_width()-page.header.images[1].winfo_width()),1)
                    self.assertEqual(page.header.images[0].winfo_y(),page.header.images[1].winfo_y());self.assertEqual(page.header.images[0].winfo_height(),page.header.images[1].winfo_height())
                    self.assertLess(page.header.facts_host.winfo_rooty(),page.header.art.winfo_rooty());self.assertFalse(page.detail_actions.winfo_manager());self.assertFalse(page.retry_row.winfo_manager())
                    self.assertFalse(page.evo_facts.values['fuel'].master.winfo_manager());self.assertTrue(page.fixed['curve'].enabled)
                    first=page.identity(page.selected);page.view_layout.details();page.neighbor(1 if page.can_step(1) else -1);self.pump(app);self.assertNotEqual(first,page.identity(page.selected));page.view_layout.listing()
                    page.query.set('no such track');self.pump(app);self.assertIsNone(page.selected);self.assertFalse(page.evo_facts.winfo_manager());self.assertFalse(page.fixed['curve'].enabled)
                    page.query.set('');self.pump(app);app.set_theme('light');app.toggle_language();self.pump(app,.25);page=app.record_loaders['best'].page
                    chosen=next(key for key,e in page.lookup.items() if e['track']=='Monza');page.table.selection_set((chosen,));self.pump(app)
                    app.root.minsize(700,600);app.root.geometry('850x700');self.pump(app,.3);self.assertEqual(page.header.columns,1)
                    self.assertTrue(page.selected);self.assertIn('samples',page.evo_facts.visible);self.assertFalse(errors)
                    photos=[page.header.picture,page.header.track_picture];app.show_page(0);self.pump(app)
                    self.assertTrue(page.disposed);self.assertTrue(all(not photo.winfo_exists() for photo in photos if photo))
                finally:
                    app.close()
                    deadline=time.monotonic()+5
                    while time.monotonic()<deadline:
                        try:
                            if not app.root.winfo_exists():break
                            app.root.update();time.sleep(.004)
                        except tk.TclError:break
            self.assertEqual({p:p.read_bytes() for p in before},before)

    def test_lmu_detail_search_refresh_and_snapshot_contract_is_unchanged(self):
        from tests.test_ui_polish64 import BestUI
        self.app=BestUI.app.__get__(self);self.mount=BestUI.mount.__get__(self)
        with patch('control_center.SIMULATOR','lmu'):
            BestUI.test_search_sort_and_note_refresh_reuse_selected_detail(self)


if __name__=='__main__':unittest.main()
