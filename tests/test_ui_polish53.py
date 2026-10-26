"""New workflows use isolated fixtures; never modify personal records or clipboard."""
import os,json,unittest,threading
from unittest.mock import patch
from types import SimpleNamespace
from tests import test_ui_efficiency as helpers


class BatchRules(unittest.TestCase):
    def test_calibration_draft_rejects_bad_points_and_cannot_override_tools(self):
        from control_video_close import validate_draft,restore_inputs
        for value in ([],dict(partial_points=[[float('nan'),1]]),dict(partial_points=[[1,2,3]]),dict(partial_target='unknown'),dict(draft_inputs=dict(marks=[]))):
            with self.assertRaises(ValueError):validate_draft(value)
        class Var:
            def __init__(self,value):self.value=value
            def set(self,value):self.value=value
        w=SimpleNamespace(fields=dict(video=Var(''),ffmpeg=Var('trusted')))
        value=dict(draft_inputs=dict(fields=dict(video='race.mp4',ffmpeg='untrusted.exe')))
        validate_draft(value);restore_inputs(w,value)
        self.assertEqual(w.fields['video'].value,'race.mp4');self.assertEqual(w.fields['ffmpeg'].value,'trusted')
    def test_stop_waits_for_current_and_retry_does_not_repeat_success(self):
        from control_batch import run_items
        stop=threading.Event();called=[];events=[]
        def operation(value):called.append(value);stop.set();return value*2
        self.assertEqual(run_items(list(enumerate([1,2,3])),operation,stop,lambda *e:events.append(e)),[(0,2,'')])
        self.assertEqual(called,[1]);self.assertEqual(events[-1],(0,'已完成',''))
        stop.clear();attempts={}
        def fail_once(value):
            attempts[value]=attempts.get(value,0)+1
            if value==2 and attempts[value]==1:raise ValueError('fixture failure')
            return value
        initial=run_items(list(enumerate([1,2,3])),fail_once,stop,lambda *e:None)
        failed=[(i,[1,2,3][i]) for i,result,error in initial if error]
        self.assertEqual(run_items(failed,fail_once,stop,lambda *e:None),[(1,2,'')]);self.assertEqual(attempts,{1:1,2:2,3:1})


@unittest.skipUnless(os.name=='nt','Native Tk')
class PolishUI(unittest.TestCase):
    app=helpers.EfficiencyTests.app;pump=helpers.EfficiencyTests.pump
    def test_profile_switch_and_close_protect_invalid_draft(self):
        from control_profile import show
        app,root,errors=self.app()
        with patch('control_confirm.draft_choice',return_value='cancel'):
            window=show(app);window.profile_variables['pressure_min'].set('unfinished');old=window.profile_car.get();window.profile_car.set('Another car');window.profile_switch()
            self.assertEqual(window.profile_car.get(),old);self.assertEqual(window.profile_variables['pressure_min'].get(),'unfinished')
        window.destroy()
        with patch('control_confirm.draft_choice',return_value='keep'):
            window=show(app);window.profile_variables['pressure_min'].set('unfinished');window.profile_close()
        self.assertTrue(app.profile_draft);window=show(app);self.assertEqual(window.profile_variables['pressure_min'].get(),'unfinished');self.assertTrue(window.profile_dirty());window.destroy();self.assertFalse(errors)
    def test_parameter_exit_cancel_and_prevalidation_prevents_partial_save(self):
        from control_forms import close_forms
        app,root,errors=self.app();app.show_page(2);self.pump(app,.5)
        forms=app.pages.pages[2].forms;forms['sampling']['fixed_hz'].set('bad');forms['vehicle']['reserve_l'].set('4')
        done=[]
        with patch('control_confirm.ask',return_value='save'),patch.object(app,'update_module') as save:
            close_forms(app,lambda:done.append(True));save.assert_not_called();self.assertFalse(done)
        self.assertEqual(forms['sampling']['fixed_hz'].get(),'bad')
        with patch('control_confirm.ask',return_value='cancel'):close_forms(app,lambda:done.append(True))
        self.assertFalse(done)
        with patch('control_confirm.ask',return_value='discard'):close_forms(app,lambda:done.append(True))
        self.assertEqual(done,[True]);self.assertFalse(errors)
    def test_mode_hints_keep_values_and_compact_search_routes(self):
        app,root,errors=self.app();app.show_page(2);self.pump(app,.5)
        values=app.pages.pages[2].forms['sampling'];original=values['min_hz'].get();values['mode'].set('fixed');values['mode'].set('dynamic');self.assertEqual(values['min_hz'].get(),original)
        search=app.settings_search;search.variable.set('hz');search.update();self.pump(app)
        self.assertLess(search.results.winfo_height(),190)
        search.variable.set('practice_recording');search.update();self.assertEqual(len(search.entries),1);search.open_first();self.assertEqual(app.root.focus_get().variable,app.practice_recording)
        search.variable.set('cache_limit_mb');search.open_first();self.pump(app);self.assertEqual(app.page,3);self.assertEqual(app.data_section,'storage');self.assertFalse(errors)
    def test_partial_parameter_write_retains_only_unfinished_changes(self):
        from control_forms import close_forms,capture
        app,root,errors=self.app();app.show_page(2);self.pump(app,.3);forms=app.pages.pages[2].forms
        forms['sampling']['fixed_hz'].set('240');forms['vehicle']['reserve_l'].set('4');saved=[];finished=[]
        def write(module,values):
            if module=='vehicle':raise OSError('fixture denied')
            saved.append(module)
        with patch('control_confirm.ask',return_value='save'),patch.object(app,'update_module',side_effect=write),patch('control_forms.messagebox.showerror'):
            close_forms(app,lambda:finished.append(True))
        self.assertEqual(saved,['sampling']);self.assertFalse(finished);drafts=capture(app.pages,app.form_drafts)
        self.assertFalse(drafts['sampling']);self.assertEqual(drafts['vehicle']['reserve_l'],'4');self.assertFalse(errors)
    def test_heading_sort_sync_selection_autofit_and_empty_reset(self):
        app,root,errors=self.app(True);app.show_page(1);self.pump(app,.5);table=app.tree;chosen=table.get_children()[0];table.selection_set((chosen,))
        table.sort_column('date');self.assertEqual(app.review_filters.state['sort'],1);self.assertEqual(table.selection(),(chosen,))
        table.sort_column('lap');self.assertEqual(app.review_filters.state['sort'],10);table.sort_column('lap');self.assertEqual(app.review_filters.state['sort'],18)
        table.layout();key,x,_=next(item for item in table.positions() if item[0]=='track');table.widths[key]=60;table.layout();edge=next(x+table.actual[k] for k,x,_ in table.positions() if k==key)
        table.autofit(SimpleNamespace(x=edge));self.assertGreater(table.widths[key],60);self.assertEqual(table.selection(),(chosen,))
        app.search.set('no_such_fixture_track');app.populate();self.assertFalse(table.get_children());table.empty_button.invoke();self.pump(app);self.assertTrue(table.get_children());self.assertEqual(app.search.get(),'');self.assertFalse(errors)
    def test_batch_ui_failure_retry_retains_success_and_safe_close(self):
        from control_batch import start
        app,root,errors=self.app();attempts={}
        def operation(value):
            attempts[value]=attempts.get(value,0)+1
            if value==2 and attempts[value]==1:raise ValueError('fixture')
            return value
        job=start(app,'赛事包导出任务',[1,2,3],operation);self.pump(app,.6);self.assertFalse(job.busy);self.assertEqual(job.states,['已完成','失败','已完成'])
        job.retry_button.invoke();self.pump(app,.5);self.assertEqual(attempts,{1:1,2:2,3:1});self.assertEqual(len(job.results),3);self.assertFalse(errors)
    def test_video_background_reopen_and_partial_calibration_save(self):
        from control_video import show
        from control_video_close import save,dirty
        app,root,errors=self.app();window=show(app,root);w=window.video_wizard;self.pump(app,.3);finish=threading.Event()
        w.dispatch(lambda:finish.wait(3),lambda _:None)
        with patch('control_confirm.ask',return_value='background'):w.close()
        self.assertTrue(window.winfo_exists());self.assertFalse(window.winfo_viewable());self.assertFalse(w.cancel.is_set());self.assertIs(show(app,root),window)
        finish.set();self.pump(app,.5);self.assertFalse(w.busy)
        w.clicks=[[10,20]];self.assertTrue(dirty(w));path=root/'calibration.json'
        w.window.withdraw()
        with patch('control_confirm.draft_choice',return_value='cancel'):self.assertFalse(w.allow_exit())
        self.assertTrue(w.window.winfo_viewable())
        w.marks.insert('1.0','T1=00:12.3')
        with patch('control_video_close.filedialog.asksaveasfilename',return_value=str(path)):self.assertTrue(save(w))
        value=json.loads(path.read_text('utf-8'));self.assertEqual(value['partial_points'],[[10,20]]);self.assertIn('T1=00:12.3',value['draft_inputs']['marks']);self.assertFalse(dirty(w));w.close();self.assertFalse(window.winfo_exists());self.assertFalse(errors)
