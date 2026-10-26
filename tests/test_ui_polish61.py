"""Regression checks for staged zone edits and training follow-up lifecycle."""
import json,os,sys,tempfile,unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from tests import test_ui_efficiency as helpers
from tests.test_career_analysis import entry

def zones():return [dict(name='区间 A',start=10.123456789,apex=50.234567891,end=100.345678912,source='user_distance'),dict(name='区间 B',start=200.,apex=250.,end=300.,source='user_distance')]
def goal(key='a',name='同名区间'):return dict(id=key*32,created_utc='2026-10-20T12:00:00Z',entry=entry(),zone=dict(name=name),baseline=dict(median_loss_s=.5,count=4))
def evaluation(g,count=3):
    return dict(goal=g,sessions=[dict(observed_utc=f'2026-10-{21+i:02d}T12:00:00Z',folder=f'fixture/{i}',time_s=20+i*.1,median_loss_s=.3+i*.01,gain_s=.2-i*.01,std_s=.01,count=4,qualified=True) for i in range(count)],errors=[],conflicts=0)


class Rules(unittest.TestCase):
    def test_zone_save_preserves_precision_unknown_fields_and_skips_identical_write(self):
        from training_zones import save,path
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as tmp:
            e=entry();p=path(tmp,e);p.parent.mkdir(parents=True);p.write_text(json.dumps(dict(custom=dict(keep=7))))
            result=save(tmp,e,zones());self.assertEqual(result[0]['start'],zones()[0]['start']);self.assertEqual(json.loads(p.read_text(encoding='utf-8'))['custom'],dict(keep=7));before=p.read_bytes()
            with patch('training_zones.atomic_json',side_effect=AssertionError('unchanged')):save(tmp,e,zones())
            self.assertEqual(p.read_bytes(),before)
    def test_corrupt_zone_settings_cannot_be_overwritten(self):
        from training_zones import save,path
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as tmp:
            p=path(tmp,entry());p.parent.mkdir(parents=True)
            for value in ('broken','[]'):
                p.write_text(value)
                with self.assertRaises(ValueError):save(tmp,entry(),zones())
                self.assertEqual(p.read_text(encoding='utf-8'),value)


@unittest.skipUnless(os.name=='nt','Native Tk')
class UI(unittest.TestCase):
    app=helpers.EfficiencyTests.app;pump=helpers.EfficiencyTests.pump
    def editor(self,app):
        from control_zone_editor import show
        e=entry();w=show(app,e,zones(),lambda:None);self.pump(app,.1);return w,w.zone_editor,e
    def goals(self,app):
        from control_training_goals import show
        g=[goal('a'),goal('b')];g[1]['id']='a'*6+'b'*26
        with patch('control_training_goals.goals',return_value=g),patch('control_training_goals.evaluate',side_effect=lambda root,g:evaluation(g)):
            w=show(app);self.pump(app,.3)
        return w,w.goal_panel,g
    def test_direct_save_includes_current_field_without_update_and_full_precision(self):
        from training_zones import load
        app,root,errors=self.app();w,p,e=self.editor(app);p.variables['name'].set('已直接保存');p.variables['end'].set('101.987654321');p.commit();self.pump(app,.3)
        self.assertFalse(w.winfo_exists());saved=load(app.data_path,e);self.assertEqual(saved[0]['name'],'已直接保存');self.assertEqual(saved[0]['start'],zones()[0]['start']);self.assertEqual(saved[0]['end'],101.987654321);self.assertFalse(errors)
    def test_invalid_switch_keeps_input_and_selection_and_never_writes(self):
        from training_zones import path
        app,root,errors=self.app();w,p,e=self.editor(app);p.variables['end'].set('oops');p.table.selection_set(('1',));self.pump(app,.1)
        self.assertEqual(p.selected,'0');self.assertEqual(p.table.selection(),('0',));self.assertEqual(p.variables['end'].get(),'oops');self.assertTrue(p.fields['end'].error);p.commit();self.assertFalse(path(app.data_path,e).exists());self.assertFalse(errors)
    def test_switch_preserves_edits_and_new_form_is_saved_once(self):
        from training_zones import load
        app,root,errors=self.app();w,p,e=self.editor(app);p.variables['name'].set('已保留');p.table.selection_set(('1',));self.pump(app,.1);self.assertEqual(dict(p.items)['0']['name'],'已保留');p.new()
        for key,value in dict(name='区间 C',start='400',apex='450',end='500').items():p.variables[key].set(value)
        p.commit();p.commit();self.pump(app,.3);values=load(app.data_path,e);self.assertEqual(len(values),3);self.assertEqual(values[0]['name'],'已保留');self.assertFalse(errors)
    def test_automatic_reset_is_staged_and_undo_retains_raw_draft(self):
        from training_zones import save,path
        app,root,errors=self.app();w,p,e=self.editor(app);save(app.data_path,e,zones());original=path(app.data_path,e).read_bytes();p.variables['start'].set('12.111111111');p.reset();p.reset();self.assertFalse(p.buttons['automatic'].enabled);self.assertEqual(path(app.data_path,e).read_bytes(),original);self.assertTrue(p.automatic);self.assertEqual(p.fields['start'].entry.cget('state'),'disabled');p.undo();self.assertFalse(p.automatic);self.assertEqual(p.variables['start'].get(),'12.111111111');p.reset();p.commit();self.pump(app,.3);self.assertFalse(path(app.data_path,e).exists());self.assertFalse(errors)
    def test_remove_is_undoable_and_cannot_save_zero_zones(self):
        app,root,errors=self.app();w,p,e=self.editor(app);p.remove();self.assertEqual(len(p.items),1);p.undo();self.assertEqual(len(p.items),2);p.remove();p.remove();p.commit();self.assertTrue(w.winfo_exists());self.assertIn('1–64',p.status.get());self.assertFalse(errors)
    def test_dirty_close_and_main_exit_protect_inputs(self):
        app,root,errors=self.app();w,p,e=self.editor(app);p.variables['name'].set('未保存')
        with patch('control_confirm.ask',return_value='cancel') as ask:p.close();app.request_close();self.assertEqual(ask.call_count,2);self.assertTrue(w.winfo_exists());self.assertFalse(app.closing)
        with patch('control_confirm.ask',return_value='save'):p.close()
        self.pump(app,.3);self.assertFalse(w.winfo_exists());self.assertFalse(errors)
    def test_zone_write_error_allows_retry_and_callbacks_are_separate(self):
        app,root,errors=self.app();w,p,e=self.editor(app);p.variables['name'].set('修改');p.callbacks=[lambda:(_ for _ in ()).throw(RuntimeError('callback fixture'))]
        with patch('control_zone_editor.persist',side_effect=OSError('write fixture')):p.commit();self.pump(app,.25)
        self.assertTrue(w.winfo_exists());self.assertTrue(p.buttons['save'].enabled);self.assertIn('write fixture',p.status.get());p.commit();self.pump(app,.3);self.assertFalse(w.winfo_exists());self.assertIn('已保存',app.status.get());self.assertFalse(errors)
    def test_zone_window_reuses_layout_identity_without_losing_draft(self):
        from control_zone_editor import show
        app,root,errors=self.app();w,p,e=self.editor(app);p.variables['name'].set('草稿');self.assertIs(show(app,dict(e,folder='other race'),zones(),lambda:None),w);self.assertEqual(p.variables['name'].get(),'草稿');self.assertFalse(errors)
    def test_goal_same_display_names_use_stable_ids_and_refresh_retains_selection(self):
        app,root,errors=self.app();w,p,g=self.goals(app);self.assertEqual(set(p.box.values),{v['id'] for v in g})
        with patch('control_training_goals.evaluate',side_effect=lambda root,g:evaluation(g)):
            p.selected.set(g[1]['id']);p.analyse();self.pump(app,.25);p.table.selection_set(('1',))
            with patch('control_training_goals.goals',return_value=list(reversed(g))):p.refresh();self.pump(app,.3)
        self.assertEqual(p.selected.get(),g[1]['id']);self.assertEqual(p.table.selection(),('1',));self.assertFalse(errors)
    def test_goal_selection_coalesces_scans_and_drops_stale_results(self):
        app,root,errors=self.app();w,p,g=self.goals(app);jobs=[]
        with patch.object(app,'run_background',side_effect=lambda work,done:jobs.append(done)):
            p.analyse();p.selected.set(g[1]['id']);p.analyse();p.selected.set(g[0]['id']);p.analyse();p.selected.set(g[1]['id']);p.analyse();self.assertEqual(len(jobs),1);self.assertFalse(p.buttons['finish'].enabled);jobs[0](evaluation(g[0]),None);self.assertEqual(len(jobs),2);self.assertIsNone(p.result);jobs[1](evaluation(g[1]),None)
        self.assertEqual(p.result['goal']['id'],g[1]['id']);self.assertTrue(p.buttons['finish'].enabled);self.assertFalse(errors)
    def test_goal_finish_failure_after_close_is_safe_and_duplicate_finish_is_locked(self):
        app,root,errors=self.app();w,p,g=self.goals(app);jobs=[]
        with patch('control_confirm.ask',return_value='finish'),patch.object(app,'run_background',side_effect=lambda work,done:jobs.append(done)):
            p.finish();p.finish();self.assertEqual(len(jobs),1);self.assertFalse(p.buttons['finish'].enabled);w.destroy();jobs[0](None,'finish fixture')
        self.assertIn('finish fixture',app.status.get());self.assertIsNone(app.training_goal_window);self.assertFalse(errors)
    def test_goal_empty_and_load_failure_can_retry(self):
        from control_training_goals import show
        app,root,errors=self.app()
        with patch('control_training_goals.goals',side_effect=OSError('read fixture')):w=show(app);self.pump(app,.25)
        p=w.goal_panel;self.assertIn('read fixture',p.status.get());self.assertTrue(p.buttons['refresh'].enabled);self.assertFalse(p.buttons['finish'].enabled)
        with patch('control_training_goals.goals',return_value=[]):p.refresh();self.pump(app,.25)
        self.assertIn('先在训练',p.status.get());self.assertEqual(p.box.cget('state'),'disabled');self.assertFalse(errors)
    def test_chart_click_selects_session_and_late_evaluation_ignores_destroyed_window(self):
        app,root,errors=self.app();w,p,g=self.goals(app);p.select_session(p.result['sessions'][0]);self.assertEqual(p.table.selection(),('0',));self.assertIn('20.000',p.details.cget('text'));jobs=[]
        with patch.object(app,'run_background',side_effect=lambda work,done:jobs.append(done)):p.analyse();w.destroy();jobs[0](evaluation(g[0]),None)
        self.assertFalse(errors)
    def test_both_windows_translate_keep_state_and_fit_minimum_size(self):
        import i18n
        app,root,errors=self.app();w,z,e=self.editor(app);other,g,goals=self.goals(app);z.variables['start'].set('12.3456789');g.table.selection_set(('1',))
        try:
            for theme in ('dark','light'):
                app.set_theme(theme)
                for language in ('en','zh'):
                    i18n.set_language(language);i18n.refresh(app.root)
                    for panel,size in ((z,'680x540'),(g,'720x540')):
                        panel.window.geometry(size);self.pump(app,.15)
                        self.assertGreater(panel.scroll.canvas.winfo_height(),150)
                        for b in panel.buttons.values():
                            if b.master is panel.actions:self.assertLessEqual(b.winfo_rootx()+b.winfo_width(),panel.window.winfo_rootx()+panel.window.winfo_width()+1);self.assertGreater(b.winfo_width(),b.font.measure(i18n.tr(b.label))+15)
            self.assertEqual(z.variables['start'].get(),'12.3456789');self.assertEqual(g.table.selection(),('1',));self.assertFalse(errors)
        finally:i18n.set_language('zh')


    def test_invalid_geometry_and_overlap_focus_fields_without_writing(self):
        from training_zones import path
        app,root,errors=self.app();w,p,e=self.editor(app)
        for value in ('nan','400','50000'):
            p.variables['end'].set(value);p.commit();self.assertTrue(w.winfo_exists());self.assertFalse(path(app.data_path,e).exists());self.assertTrue(p.fields['end'].error)
        self.assertFalse(errors)
    def test_save_in_progress_defers_exit_and_tracks_failure_without_closing(self):
        app,root,errors=self.app();w,p,e=self.editor(app);p.variables['name'].set('保存中');jobs=[];closed=[]
        with patch.object(app,'run_background',side_effect=lambda work,done:jobs.append((work,done))):
            p.commit();p.close(lambda:closed.append(True),exiting=True);self.assertTrue(w.winfo_exists());jobs[0][1](None,'write fixture');self.assertFalse(closed);self.assertTrue(w.winfo_exists());p.commit(lambda:closed.append(True));jobs[1][0]();jobs[1][1](None,None)
        self.assertEqual(closed,[True]);self.assertFalse(w.winfo_exists());self.assertFalse(errors)
    def test_goal_finish_retains_reference_and_unknown_data_in_file(self):
        from control_training_goals import show
        app,root,errors=self.app();g=[goal('a'),goal('b')];folder=app.data_path/'PersonalRecords/TrainingGoals';folder.mkdir(parents=True)
        for v in g:(folder/(v['id']+'.json')).write_text(json.dumps(dict(v,version=1,status='active',reference=dict(keep=[1,2,3]),custom='preserve')))
        with patch('control_training_goals.evaluate',side_effect=lambda root,g:evaluation(g)):
            w=show(app);self.pump(app,.3);p=w.goal_panel
            with patch('control_confirm.ask',return_value='finish'):p.finish();self.pump(app,.35)
        first=json.loads((folder/(g[0]['id']+'.json')).read_text(encoding='utf-8'));second=json.loads((folder/(g[1]['id']+'.json')).read_text(encoding='utf-8'));self.assertEqual(first['status'],'closed');self.assertEqual(first['reference'],dict(keep=[1,2,3]));self.assertEqual(first['custom'],'preserve');self.assertEqual(second['status'],'active');self.assertEqual(p.selected.get(),g[1]['id']);self.assertFalse(errors)
    def test_goal_refresh_and_translation_keep_scroll_and_scan_error_is_retryable(self):
        import i18n
        app,root,errors=self.app();w,p,g=self.goals(app)
        with patch('control_training_goals.evaluate',side_effect=lambda root,g:evaluation(g,8)):
            p.analyse();self.pump(app,.25);p.table.selection_set(('6',));p.table.set_offset(100);self.pump(app,.1);offset=p.table.offset
            i18n.set_language('en');i18n.refresh(app.root);self.pump(app,.1);self.assertEqual(p.table.offset,offset)
            with patch('control_training_goals.goals',return_value=g):p.refresh();self.pump(app,.3)
            self.assertEqual(p.table.selection(),('6',));self.assertEqual(p.table.offset,offset)
        i18n.set_language('zh')
        with patch('control_training_goals.evaluate',side_effect=OSError('scan fixture')):p.analyse();self.pump(app,.25)
        self.assertIn('scan fixture',p.status.get());self.assertTrue(p.buttons['refresh'].enabled);self.assertIsNone(p.result);self.assertFalse(errors)
