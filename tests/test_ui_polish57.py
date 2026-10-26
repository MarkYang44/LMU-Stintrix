"""Regression coverage for car-profile editing and independent lap selections."""
import json,os,sys,threading,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from tests import test_ui_efficiency as helpers


def records(root,count=3):
    return [dict(folder=str(root/f'Logs/{i}'),key=f'Logs/{i}',track='Monza',track_layout='Monza',track_length_m=5793,vehicle='BMW M4 LMGT3',date=f'2026-10-2{i}',session_type='Race',status='complete') for i in range(count)]

LAPS=[dict(number=1,time_s=111.6,track_length_m=5793),dict(number=2,time_s=110.2,track_length_m=5793)]


@unittest.skipUnless(os.name=='nt','Native Tk')
class UI(unittest.TestCase):
    app=helpers.EfficiencyTests.app;pump=helpers.EfficiencyTests.pump
    def pair(self,app,root,items=None):
        from control_lap_pair import show
        items=items or records(root)
        for target,value in [('inventory',items),('valid_laps',LAPS)]:
            guard=patch('control_lap_pair.'+target,return_value=value);guard.start();self.addCleanup(guard.stop)
        guard=patch('control_lap_pair.finished_metadata',side_effect=lambda folder:next(v for v in items if Path(v['folder'])==Path(folder)));guard.start();self.addCleanup(guard.stop)
        w=show(app,root);self.pump(app,.4);return w,w.pair_controls
    def profile(self,app,root):
        import vehiclelab
        from control_profile import show
        value=vehiclelab.settings(dict(record_hz=20,reserve_l=7,profiles={'*':dict(vehiclelab.DEFAULT_PROFILE,temp_min=72),'BMW':dict(vehiclelab.DEFAULT_PROFILE,temp_min=80)}))
        (root/'vehicle_settings.json').write_text(json.dumps(value),'utf-8')
        guard=patch('control_settings.ROOT',root);guard.start();self.addCleanup(guard.stop)
        with patch('library.inventory',return_value=[dict(vehicle='Ferrari'),dict(vehicle='BMW')]):w=show(app);self.pump(app,.3)
        return w
    def test_offline_recorded_car_inherits_without_writing_and_can_be_saved(self):
        app,root,errors=self.app();w=self.profile(app,root);p=root/'vehicle_settings.json';before=p.read_bytes()
        self.assertIn('Ferrari',w.profile_box.values);w.profile_car.set('Ferrari');w.profile_switch()
        self.assertIn('沿用',w.profile_source.get());self.assertEqual(float(w.profile_variables['temp_min'].get()),72);self.assertEqual(p.read_bytes(),before)
        w.profile_buttons['save'].invoke();self.assertTrue(w.winfo_exists());self.assertFalse(w.profile_dirty());saved=json.loads(p.read_text('utf-8'))
        self.assertEqual(saved['profiles']['Ferrari']['temp_min'],72);self.assertEqual(saved['profiles']['BMW']['temp_min'],80);self.assertEqual(saved['record_hz'],20);self.assertEqual(saved['reserve_l'],7);self.assertIn('已保存',w.profile_source.get());self.assertFalse(errors)
    def test_profile_default_loading_and_undo_are_only_drafts(self):
        app,root,errors=self.app();w=self.profile(app,root);w.profile_car.set('BMW');w.profile_switch();p=root/'vehicle_settings.json';before=p.read_bytes()
        w.profile_buttons['defaults'].invoke();self.assertEqual(float(w.profile_variables['temp_min'].get()),72);self.assertTrue(w.profile_dirty());self.assertEqual(p.read_bytes(),before)
        w.profile_buttons['reset'].invoke();self.assertEqual(float(w.profile_variables['temp_min'].get()),80);self.assertFalse(w.profile_dirty());self.assertEqual(p.read_bytes(),before)
        w.profile_car.set('*');w.profile_switch();w.profile_buttons['defaults'].invoke();self.assertEqual(float(w.profile_variables['temp_min'].get()),60);self.assertEqual(p.read_bytes(),before);self.assertFalse(errors)
    def test_profile_ctrl_s_stays_open_validates_and_escape_uses_guard(self):
        app,root,errors=self.app();w=self.profile(app,root);p=root/'vehicle_settings.json';before=p.read_bytes();field=w.profile_fields['pressure_min'].entry
        w.focus_force();field.focus_set();self.pump(app,.05);w.profile_variables['pressure_min'].set('bad');field.event_generate('<Control-s>');self.pump(app,.05)
        self.assertTrue(w.profile_fields['pressure_min'].error);self.assertEqual(p.read_bytes(),before)
        w.profile_variables['pressure_min'].set('145');field.event_generate('<Control-s>');self.pump(app,.05);self.assertTrue(w.winfo_exists());self.assertFalse(w.profile_dirty());self.assertEqual(json.loads(p.read_text('utf-8'))['profiles']['*']['pressure_min'],145)
        w.profile_variables['pressure_min'].set('146')
        with patch('control_confirm.ask',return_value='cancel') as ask:field.event_generate('<Escape>');self.pump(app,.05);ask.assert_called_once()
        self.assertTrue(w.winfo_exists());self.assertTrue(w.profile_dirty());self.assertFalse(errors)
    def test_existing_profile_search_scrolls_target_into_view(self):
        from control_profile import show
        app,root,errors=self.app();w=self.profile(app,root);w.geometry('620x650');self.pump(app,.1);same=show(app,target='wear_min');self.pump(app,.1)
        field=w.profile_fields['wear_min'];canvas=w.profile_page.canvas;self.assertIs(same,w);self.assertIs(w.focus_get(),field.entry);self.assertGreaterEqual(field.winfo_rooty(),canvas.winfo_rooty());self.assertLessEqual(field.winfo_rooty()+field.winfo_height(),canvas.winfo_rooty()+canvas.winfo_height()+1);self.assertFalse(errors)
    def test_pair_reuse_changes_only_requested_side_and_keeps_search(self):
        from control_lap_pair import show
        app,root,errors=self.app();w,c=self.pair(app,root);b=c['events']['B'].get();number=c['numbers']['B'].get();c['query'].set('no matches')
        with patch('control_lap_pair.valid_laps',return_value=LAPS) as scan:
            same=show(app,root,[root/'Logs/1']);self.pump(app,.3);self.assertIs(same,w);scan.assert_called_once_with(str(root/'Logs/1'))
        self.assertEqual(c['events']['B'].get(),b);self.assertEqual(c['numbers']['B'].get(),number);self.assertEqual(c['query'].get(),'no matches');self.assertIn('2026-10-21',c['events']['A'].get());self.assertFalse(errors)
    def test_pair_reuse_during_inventory_uses_latest_request(self):
        from control_lap_pair import show
        app,root,errors=self.app();items=records(root);jobs=[]
        with patch.object(app,'run_background',side_effect=lambda work,done:jobs.append((work,done))),patch('control_lap_pair.inventory',return_value=items),patch('control_lap_pair.valid_laps',return_value=LAPS),patch('control_lap_pair.finished_metadata',return_value=items[0]):
            w=show(app,root,[root/'Logs/0']);show(app,root,[root/'Logs/2',root/'Logs/1'])
            while jobs:work,done=jobs.pop(0);done(work(),None)
        c=w.pair_controls;self.assertIn('2026-10-22',c['events']['A'].get());self.assertIn('2026-10-21',c['events']['B'].get());self.assertFalse(errors)
    def test_pair_unknown_new_event_refreshes_inventory_and_keeps_other_lap(self):
        from control_lap_pair import show
        app,root,errors=self.app();items=records(root);w,c=self.pair(app,root,items);b=c['events']['B'].get();number=c['numbers']['B'].get();new=records(root,4)[-1];items.append(new)
        with patch('control_lap_pair.inventory',return_value=items) as inv,patch('control_lap_pair.valid_laps',return_value=LAPS) as scan:
            show(app,root,[root/'Logs/3']);self.pump(app,.4);inv.assert_called_once();scan.assert_called_once_with(str(root/'Logs/3'))
        self.assertEqual(c['events']['B'].get(),b);self.assertEqual(c['numbers']['B'].get(),number);self.assertIn('2026-10-23',c['events']['A'].get());self.assertFalse(errors)
    def test_comparison_freezes_all_choices_and_reopens_result_after_browser_failure(self):
        from control_lap_pair import show
        app,root,errors=self.app();w,c=self.pair(app,root);entered=threading.Event();gate=threading.Event();result=root/'comparison.html';result.write_text('fixture','utf-8');chosen=[v.get() for v in c['events'].values()]
        def export(*args):entered.set();gate.wait(4);return dict(comparison=str(result))
        try:
            with patch('control_lap_pair.export_pair',side_effect=export) as generate,patch('control_lap_pair.os.startfile',side_effect=OSError('browser fixture')):
                c['compare'].invoke();self.assertTrue(entered.wait(1));self.assertTrue(all(b.cget('state')=='disabled' for b in [*c['event_boxes'].values(),*c['lap_boxes'].values()]));show(app,root,[root/'Logs/1']);self.assertEqual([v.get() for v in c['events'].values()],chosen)
                gate.set();self.pump(app,.4);self.assertTrue(c['reopen'].enabled);self.assertIn('browser fixture',c['status'].get())
                with patch('control_lap_pair.os.startfile') as opened:c['reopen'].invoke();opened.assert_called_once_with(str(result))
                generate.assert_called_once();self.assertTrue(all(b.cget('state')=='readonly' for b in [*c['event_boxes'].values(),*c['lap_boxes'].values()]));result.unlink();c['reopen'].invoke();self.assertIn('移动或删除',c['status'].get())
        finally:gate.set()
        self.assertFalse(errors)
    def test_old_scan_result_and_closed_profile_callbacks_do_not_overwrite(self):
        from control_lap_pair import show
        from control_profile import show as profile
        app,root,errors=self.app();items=records(root);jobs=[]
        with patch.object(app,'run_background',side_effect=lambda work,done:jobs.append((work,done))),patch('control_lap_pair.inventory',return_value=items):
            w=show(app,root);work,done=jobs.pop(0);done(work(),None);a_old=jobs.pop(0)[1];jobs.pop(0)
            c=w.pair_controls;c['events']['A'].set(list(c['state']['events'])[1]);c['scan']('A');a_new=jobs.pop(0)[1]
            a_new(dict(laps=LAPS,session=items[1]),None);a_old(dict(laps=[dict(number=9,time_s=1)],session=items[0]),None);self.assertNotIn(9,c['state']['rows']['A'])
            p=profile(app);work,done=jobs.pop(0);p.destroy();done([dict(vehicle='Late')],None)
        self.assertFalse(errors)

if __name__=='__main__':unittest.main()
