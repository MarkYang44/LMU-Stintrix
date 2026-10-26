"""Merged event actions, Chinese search, and readable record conditions."""
import copy,json,os,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
import i18n
from track_names import display,layout
from record_presentation import present
from tests import test_personal_records as fixtures
from laps import export_fastest


class ReviewLayoutTests(unittest.TestCase):
    def test_chinese_names_cover_catalog_and_recorded_aliases_without_mutating_identity(self):
        catalog=json.loads((ROOT/'src/guide/catalog.json').read_text(encoding='utf-8'))
        for track in catalog['tracks'].values():
            self.assertNotEqual(display(track['name'],'zh'),track['name'])
            self.assertEqual(display(track['name'],'en'),track['name'])
        self.assertEqual(display('Autódromo José Carlos Pace','zh'),'英特拉格斯赛道')
        self.assertEqual(display('Michelin Raceway Road Atlanta','zh'),'亚特兰大之路赛道')
        self.assertEqual(display('Algarve International Circuit','zh'),'波尔蒂芒赛道')
        self.assertEqual(display('Algarve International Circuit','en'),'Algarve International Circuit')
        self.assertEqual(layout('Algarve International Circuit','Algarve International Circuit',4653),'波尔蒂芒赛道 · 4.653 km')
        self.assertEqual(layout('Algarve International Circuit','Algarve International Circuit GP',4653),'大奖赛布局 · 4.653 km')
        self.assertEqual(display('Unknown test circuit','zh'),'Unknown test circuit')
        self.assertEqual(layout('Monza','Monza',5780.6),'蒙扎国家赛车场 · 5.781 km')

    def test_detail_summary_groups_units_and_keeps_only_simple_tire_conditions(self):
        entry=dict(track='Autodromo Nazionale Monza',layout='Autodromo Nazionale Monza',length_m=5780.6,time_s=118.396,
            vehicle_class='LMGT3',session=dict(vehicle='BMW M4 LMGT3',started_utc='2026-10-09T14:55:47.274507+00:00'),lap=dict(number=4))
        detail=dict(conditions=dict(fuel_l=73.412,track_temp_c=33.29,wetness=0,tc_level=7,abs_level=6,tyre_front_name='Medium'),
            vehicle_summary={'fl_wear_fraction':{'start':.9625},'fr_wear_fraction':{'start':.9713},'fl_pressure_kpa':{'start':173.16}})
        before=copy.deepcopy((entry,detail));value=present(entry,detail)
        self.assertEqual(value['track'],'蒙扎国家赛车场');self.assertEqual(value['time'],'1:58.396')
        self.assertIn('2026-10-09 14:55 UTC',value['context']);self.assertNotIn('.274507',value['context'])
        self.assertEqual(value['car_metrics']['fuel'],'73.4 L');self.assertEqual(value['car_metrics']['front'],'中性胎')
        self.assertEqual(value['car_metrics']['rear'],'未知');self.assertEqual(value['car_metrics']['remaining'],'96.2 %')
        self.assertEqual(value['track_metrics']['wetness'],'干燥');self.assertEqual(value['car_metrics']['assists'],'TC 7 / ABS 6')
        self.assertNotIn('173.16',str(value));self.assertEqual((entry,detail),before)

    @unittest.skipUnless(os.name=='nt','Native Windows UI')
    def test_merged_actions_chinese_filter_and_responsive_detail_tiles(self):
        import control_center
        from control_widgets import Pill
        from control_metrics import Metrics
        from control_list import SessionList
        from control_fields import Field
        errors=[]
        def walk(widget):
            for child in widget.winfo_children():yield child;yield from walk(child)
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as directory,patch('control_center.ROOT',Path(directory)),patch('control_center.ControlCenter.repair_windows_entry'):
            folder=fixtures.FeatureTests().session(directory,'monza',track='Autodromo Nazionale Monza')
            export_fastest(folder,ROOT/'src/compare.html')
            center=control_center.ControlCenter();center.root.report_callback_exception=lambda *args:errors.append(str(args))
            def wait(condition):
                deadline=time.monotonic()+4
                while time.monotonic()<deadline:
                    center.root.update();time.sleep(.01)
                    if condition():return
                self.fail('Native UI did not settle')
            try:
                self.assertNotIn('曲线对比',control_center.PAGES);self.assertEqual(len(control_center.PAGES),7)
                center.show_page(1);wait(lambda:bool(center.tree.get_children()))
                labels={w.label for w in walk(center.shell.action_host) if isinstance(w,Pill)}
                labels.update(a.label for a in center.review_menu.actions)
                self.assertTrue({'打开赛事复盘','圈速单','比赛日志','圈 A / 圈 B','跨场最快圈对比','查看最快圈','导出赛事包'}.issubset(labels))
                center.search.set('蒙扎');center.populate();self.assertEqual(len(center.tree.get_children()),1)
                self.assertEqual(center.tree.rows['0'][center.tree.columns.index('track')],'蒙扎国家赛车场')
                center.search.set('Monza');center.populate();self.assertEqual(len(center.tree.get_children()),1)
                center.show_page(6);wait(lambda:'条个人赛道纪录' in center.status.get())
                grids=[w for w in walk(center.content) if isinstance(w,Metrics)]
                wait(lambda:all(w.values[next(iter(w.values))].cget('text')!='—' for w in grids))
                self.assertEqual(len(grids),2);self.assertEqual(len(grids[1].values),5)
                table=next(w for w in walk(center.content) if isinstance(w,SessionList));self.assertEqual(table.rows['0'][0],'蒙扎国家赛车场')
                field=next(w for w in walk(center.content) if isinstance(w,Field));field.entry.delete(0,'end');field.entry.insert(0,'蒙扎')
                wait(lambda:len(table.get_children())==1)
                center.toggle_language();wait(lambda:'personal track records' in center.status.get())
                table=next(w for w in walk(center.content) if isinstance(w,SessionList));self.assertEqual(table.rows['0'][0],'Autodromo Nazionale Monza')
                self.assertFalse(errors,errors)
            finally:center.close();i18n.set_language('zh')


if __name__=='__main__':unittest.main()
