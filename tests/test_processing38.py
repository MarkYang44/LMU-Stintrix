"""Per-job matching and visible, individually removable analysis scope choices."""
import json,math,os,unittest
from unittest.mock import patch
from tests import test_career_analysis as fixtures


class Processing(unittest.TestCase):
    def test_prepared_matcher_snapshots_settings_once_but_checks_every_candidate(self):
        import condition_match as c
        reference=fixtures.conditions();policy=dict(c.DEFAULTS);saved=dict(reference)
        with patch('condition_match.settings',wraps=c.settings) as read:
            accept=c.matcher(reference,policy)
            for i in range(30):
                value=accept(dict(saved,fuel_l=30+(i%4)))
                self.assertEqual(value['allowed'],i%4<=2)
                self.assertEqual(value['different'],[] if i%4<=2 else ['fuel_l'])
            self.assertEqual(read.call_count,1)
            for key in ('fuel_l','track_temp_c','ambient_temp_c','wetness','rain','track_grip','tc_level','abs_level'):
                for invalid in (None,True,'1',math.nan,math.inf):
                    result=accept(dict(saved,**{key:invalid}));self.assertFalse(result['allowed']);self.assertEqual(result['unknown'],[key]);self.assertEqual(result['different'],[])
            self.assertEqual(read.call_count,1)
        reference['fuel_l']=80.;policy['fuel_l']=0.;policy['include_unknown']=True
        self.assertTrue(accept(saved)['allowed']);self.assertFalse(c.match(reference,saved,policy)['allowed'])
        for bad in (dict(fuel_l=-1),dict(rain=math.inf),dict(include_unknown=1),dict(min_laps=2)):
            with self.assertRaises(ValueError):c.matcher(saved,bad)
            with self.assertRaises(ValueError):c.match(saved,saved,bad)
        self.assertFalse(accept(dict(saved,fuel_l=2001))['allowed'])


@unittest.skipUnless(os.name=='nt','Native Windows Tk')
class UI(unittest.TestCase):
    from tests import test_ui_polish60 as helpers
    app=helpers.UI.app;pump=helpers.UI.pump;panel=helpers.UI.panel

    def test_training_tags_remove_only_one_flag_coalesce_analysis_and_lock_during_writes(self):
        app,root,errors=self.app();window,p,e=self.panel(app,root);self.assertFalse(p.scope.winfo_manager());self.assertFalse(p.scope.chips.winfo_manager())
        p.table.selection_set(('1',));selected=p.zone_state['selected']['name']
        for var in p.policies.values():var.set(True)
        self.assertEqual(set(p.scope.chips.buttons),set(p.policies));self.assertFalse(p.scope.winfo_manager())
        calls=[];p.scanner=lambda policy:(calls.append(policy),self.helpers.training())[1]
        p.scope.chips.buttons['cross_mode'].invoke();p.scope.chips.buttons['include_unknown'].invoke();self.assertFalse(calls)
        self.assertFalse(p.policies['cross_mode'].get());self.assertTrue(p.policies['cross_phase'].get());self.pump(app,.35)
        self.assertEqual(len(calls),1);self.assertFalse(calls[0]['include_unknown']);self.assertTrue(calls[0]['cross_phase']);self.assertEqual(p.zone_state['selected']['name'],selected)
        for flag in ('exporting','writing'):
            setattr(p,flag,True);p.sync();self.assertFalse(p.scope.chips.buttons['cross_phase'].enabled);p.scope.chips.remove('cross_phase');self.assertTrue(p.policies['cross_phase'].get());setattr(p,flag,False);p.sync()
        self.assertTrue(p.scope.chips.buttons['cross_phase'].enabled);self.assertFalse(errors)

    def test_comparable_tags_keep_draft_selection_and_settings_in_small_english_layout(self):
        from condition_match import DEFAULTS
        app,root,errors=self.app();path=root/'PersonalRecords/comparable_settings.json';path.parent.mkdir(exist_ok=True);path.write_text(json.dumps(dict(DEFAULTS,include_unknown=True,cross_mode=True,cross_phase=True)))
        window,p,e=self.panel(app,root,'comparable');before=path.read_bytes();p.table.selection_set(('0',));selected=p.selection_state['selected']['folder'];jobs=[]
        with patch.object(app,'run_background',side_effect=lambda work,done:jobs.append((work,done))):
            app.set_theme('light');app.toggle_language();window.maxsize(4096,4096);window.geometry('780x560');self.pump(app,.2)
            chips=p.scope.chips;self.assertEqual(len(chips.buttons),3);self.assertFalse(p.scope.winfo_manager());self.assertFalse(jobs)
            self.assertIn('unknown',chips.buttons['include_unknown'].full_text.lower())
            for b in chips.buttons.values():self.assertLessEqual(b.winfo_x()+b.winfo_width(),chips.winfo_width())
            chips.buttons['cross_mode'].invoke();self.assertFalse(p.flags['cross_mode'].get());self.assertTrue(p.flags['include_unknown'].get());self.assertFalse(jobs);self.assertFalse(p.ready());self.assertEqual(path.read_bytes(),before);self.assertEqual(p.selection_state['selected']['folder'],selected)
            chips.buttons['include_unknown'].invoke();chips.buttons['cross_phase'].invoke();self.assertFalse(chips.winfo_manager());self.assertFalse(p.scope.winfo_manager())
        p.edited=False;self.assertFalse(errors)


if __name__=='__main__':unittest.main()
