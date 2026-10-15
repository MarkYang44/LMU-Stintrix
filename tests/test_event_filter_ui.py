"""Native workflow with explicit synthetic fixtures, including saved views."""
import json,sys,time,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))

class EventFilterUITests(unittest.TestCase):
 def test_five_views_presets_notes_layouts_and_filtered_pb_have_no_callback_errors(self):
  import control_center,i18n
  from control_event_filters import EventControls,edit_note
  from control_list import SessionList
  from control_widgets import Pill
  from tests.test_personal_records import FeatureTests
  from laps import export_fastest
  from tests.test_event_catalog import write
  def walk(w):
   for c in w.winfo_children():yield c;yield from walk(c)
  with tempfile.TemporaryDirectory(dir=ROOT/'_local') as tmp,patch('control_center.ROOT',Path(tmp)),patch('control_center.ControlCenter.repair_windows_entry'):
   for i,(layout,car,wet) in enumerate((('GP','BMW M4 LMGT3',.4),('GP','BMW M4 LMGT3',0),('Short','Porsche 911 GT3 R LMGT3',0))):
    folder=FeatureTests().session(tmp,str(i),track='Monza',track_layout=layout,vehicle=car,vehicle_class='LMGT3',session=10,driver='SYNTHETIC UI FIXTURE',started_utc=f'2026-10-{i+10:02}T10:00:00Z',ended_utc=f'2026-10-{i+10:02}T10:30:00Z')
    export_fastest(folder,ROOT/'src/compare.html');p=folder/'fastest_lap_summary.json';v=json.loads(p.read_text());v['conditions']=dict(wetness=wet,rain=0,fuel_l=20,tyre_front_name='Medium',tyre_rear_name='Medium');v['lap']['time_s']=90+i;write(p,v)
    write(folder/'race_summary.json',dict(finish_flag=1,available=True,vehicle_class='LMGT3',class_position_available=True,finish_place=i+1,finish_class_place=i+1,grid_place=8,grid_class_place=8,class_size=20,team='Synthetic Team'))
   xml=Path(tmp)/'source.xml';xml.write_text('<SyntheticFixture/>')
   official=dict(id='synthetic',source_xml=str(xml),phase='Race',race_mode='single',track='Monza',layout='GP',length_m=1000,vehicle='BMW M4 LMGT3',vehicle_class='LMGT3',driver='SYNTHETIC UI FIXTURE',team='Synthetic Team',started_utc='2026-10-14T10:00:00Z',finished=True,finish_status='Finished Normally',grid_place=8,grid_class_place=5,finish_place=3,finish_class_place=2,best_lap_s=95,finish_time_s=1800,completed_laps=20,pit_stops=1,class_size=20,link_status='unmatched',laps=[dict(number=1,time_s=95,sectors=[30,30,35])])
   write(Path(tmp)/'library_notes.json',{'OfficialResults/events/synthetic':dict(text='Official annotation')})
   write(Path(tmp)/'OfficialResults/index.json',dict(version=1,entries=[official],errors=[],conflicts=[]))
   center=control_center.ControlCenter();errors=[];center.root.report_callback_exception=lambda *args:errors.append(str(args))
   def wait(condition):
    deadline=time.monotonic()+8
    while time.monotonic()<deadline:
     center.root.update();time.sleep(.01)
     if errors:self.fail(str(errors))
     if condition():return
    self.fail('Native UI did not settle: '+center.status.get()+' / '+str([(w.cget('text') if 'text' in w.keys() else '') for w in walk(center.content) if w.winfo_class()=='Label'])[-2000:])
   def controls():return next(w for w in walk(center.content) if isinstance(w,EventControls))
   def table():return next(w for w in walk(center.content) if isinstance(w,SessionList))
   def use(**state):
    c=controls();c.state.update(state);c.update_options(c.items);c.callback();center.root.update();return c
   try:
    center.show_page(1);wait(lambda:center.tree is not None and len(center.tree.rows)==3)
    c=use(track='Monza',vehicle_class='LMGT3');c.toggle();center.root.update();self.assertTrue(c.advanced.winfo_manager());self.assertTrue(c.chip_widgets)
    use(weather='dry');self.assertEqual(len(center.tree.rows),2)
    with patch('control_event_filters.simpledialog.askstring',return_value='Synthetic dry laps'):c.save_view()
    c.reset();center.root.update();self.assertEqual(len(center.tree.rows),3);c.view.set('Synthetic dry laps');c.restore();center.root.update();self.assertEqual(len(center.tree.rows),2)
    center.tree.selection_set((next(iter(center.tree.rows)),));chosen=center.items[int(center.tree.selection()[0])]
    edit_note(center,chosen,center.refresh);window=next(w for w in center.root.winfo_children() if w.winfo_class()=='Toplevel')
    from control_widgets import Switch
    next(w for w in walk(window) if isinstance(w,Switch)).variable.set(True)
    next(w for w in walk(window) if isinstance(w,Pill) and w.label=='保存标记').command();wait(lambda:any(v.get('favorite') for v in center.items))
    use(favorite='yes');self.assertEqual(len(center.tree.rows),1);c.reset()
    center.personal_record_view='best';center.show_page(6);wait(lambda:bool(table().rows))
    use(weather='dry',car='BMW M4 LMGT3');self.assertEqual(len(table().rows),1);self.assertEqual(next(iter(table().rows.values()))[-1],'1:31.000')
    for kind in ('podium','history','official'):
     center.personal_record_view=kind;center.show_page(6);wait(lambda:bool(table().rows));self.assertIsInstance(controls(),EventControls)
     c=controls();c.state['mode']='single' if kind=='official' else '';c.update_options(c.items);c.callback();center.root.update();self.assertTrue(table().rows)
     if kind=='official':
      c.query.set('Official annotation');center.root.update();self.assertEqual(len(table().rows),1);c.query.set('')
      use(weather='unknown');self.assertEqual(len(table().rows),1);use(weather='dry');self.assertFalse(table().rows);c.reset()
    center.toggle_language();wait(lambda:bool(table().rows));self.assertEqual(controls().choices['trust'].values[0],'All evidence')
    center.toggle_theme();center.root.update();self.assertFalse(errors,errors)
   finally:center.close();i18n.set_language('zh')

if __name__=='__main__':unittest.main()
