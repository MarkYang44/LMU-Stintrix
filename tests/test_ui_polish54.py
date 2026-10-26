"""Workflow tests use private temporary fixtures and mocked publication/clipboard paths."""
import os,json,unittest,threading
from pathlib import Path
from unittest.mock import patch
from tests import test_ui_efficiency as helpers


class Rules(unittest.TestCase):
    def test_note_limits_are_explicit_and_never_truncate(self):
        from control_notes import checked
        self.assertEqual(checked('A， A, B','a\nb'),['A','B'])
        for tags,text in [('x'*41,''),(','.join(str(i) for i in range(21)),''),('', 'x'*2001)]:
            with self.assertRaises(ValueError):checked(tags,text)
        self.assertEqual(checked('', 'x'*2000),[])


@unittest.skipUnless(os.name=='nt','Native Tk')
class UI(unittest.TestCase):
    app=helpers.EfficiencyTests.app;pump=helpers.EfficiencyTests.pump
    def test_light_to_dark_keeps_headings_and_primary_text_distinct(self):
        from control_theme import T
        app,root,errors=self.app();app.show_page(2);self.pump(app,.2)
        for _ in range(2):
            app.set_theme('light');app.set_theme('dark');self.pump(app,.1)
            from i18n import tr
            body=app.form_panels['sampling'];heading=next(w for w in body.winfo_children() if w.winfo_class()=='Label' and w.cget('text')==tr('输入采样与 HUD 刷新'))
            self.assertEqual(heading.cget('foreground'),T.FG)
            def walk(widget):
                for child in widget.winfo_children():yield child;yield from walk(child)
            primary=next(w for w in walk(body) if getattr(w,'primary',False));variable=app.pages.pages[2].forms['sampling']['fixed_hz'];previous=variable.get()
            try:
                variable.set('240' if previous!='240' else '120');self.pump(app,.05);self.assertTrue(primary.enabled);self.assertEqual(primary.itemcget(primary.caption,'fill'),T.INK)
            finally:variable.set(previous)
        self.assertFalse(errors)
    def test_multiline_note_limits_keep_reopen_save_and_unknown_fields(self):
        from control_notes import show
        app,root,errors=self.app();folder=root/'Logs/fixture';folder.mkdir(parents=True);path=root/'library_notes.json';key=str(folder.relative_to(root))
        path.write_text(json.dumps({key:{'custom':17,'text':'old'},'other':{'tags':['Practice']}}),'utf-8');entry=dict(folder=str(folder));done=[]
        w=show(app,entry,lambda:done.append(True));c=w.note_controls;c['text'].delete('1.0','end');c['text'].insert('1.0','x'*2001)
        before=path.read_bytes();self.assertFalse(c['save']());self.assertEqual(path.read_bytes(),before);self.assertTrue(w.winfo_exists())
        c['text'].delete('1.0','end');c['text'].insert('1.0','First line\nSecond line');c['choice'].set('Practice');c['add']()
        with patch('control_notes.draft_choice',return_value='keep'):c['close']()
        self.assertTrue(app.note_drafts);w=show(app,entry,lambda:done.append(True));self.assertEqual(w.note_controls['text'].get('1.0','end-1c'),'First line\nSecond line');self.assertTrue(w.note_controls['save']())
        saved=json.loads(path.read_text('utf-8'))[key];self.assertEqual(saved['custom'],17);self.assertEqual(saved['tags'],['Practice']);self.assertEqual(done,[True]);self.assertFalse(app.note_drafts);self.assertFalse(errors)
        w=show(app,entry,lambda:None);w.note_controls['text'].insert('end','new');path.write_text('unreadable external edit','utf-8')
        self.assertFalse(w.note_controls['save']());self.assertEqual(path.read_text('utf-8'),'unreadable external edit');self.assertTrue(w.winfo_exists());w.destroy()
    def test_batch_history_retains_failed_and_blocks_second_worker(self):
        from control_batch import start,show,running
        app,root,errors=self.app();calls=[]
        def operation(v):
            calls.append(v)
            if len(calls)==1:raise ValueError('fixture')
            return v
        first=start(app,'赛事包导出任务',[1],operation);self.pump(app,.4);self.assertEqual(first.states,['失败'])
        gate=threading.Event()
        try:
            second=start(app,'赛事包导入任务',[2],lambda v:gate.wait(3));self.pump(app,.1)
            app.batch_job=first;show(app);first.retry_button.invoke();self.assertEqual(calls,[1]);self.assertIs(running(app),second)
            self.assertIs(start(app,'存储处理任务',[3],operation),second);self.assertEqual(len(app.batch_jobs),2)
        finally:gate.set()
        self.pump(app,.4);first.retry_button.invoke();self.pump(app,.4);self.assertEqual(calls,[1,1]);self.assertEqual(first.states,['已完成']);self.assertTrue(first.window.winfo_exists());self.assertFalse(errors)
    def test_form_bar_reset_and_ctrl_s_apply_only_current_module(self):
        app,root,errors=self.app();app.show_page(2);self.pump(app,.3);forms=app.pages.pages[2].forms;bar=app.form_bar
        forms['sampling']['fixed_hz'].set('240');forms['vehicle']['reserve_l'].set('4');bar.current='vehicle';bar.refresh();self.assertTrue(bar.packed);bar.discard()
        self.assertEqual(forms['sampling']['fixed_hz'].get(),'240');self.assertFalse(app.form_panels['vehicle'].form_changed())
        bar.current='sampling'
        def save(module,values):
            self.assertEqual(module,'sampling')
            from sampling import save_settings,load_settings
            path=root/'settings.json';save_settings(path,{**load_settings(path),**values})
        field=app.form_panels['sampling'].form_feedback.fields['fixed_hz'][0].entry;app.root.focus_force();field.focus_set();self.pump(app,.05)
        with patch.object(app,'update_module',side_effect=save) as apply:field.event_generate('<Control-s>');self.pump(app,.05);apply.assert_called_once()
        self.assertFalse(bar.packed);self.assertFalse(app.form_panels['sampling'].form_changed());app.show_page(0);self.pump(app,.1);self.assertFalse(bar.winfo_exists());self.assertFalse(errors)
    def test_guide_search_shortcuts_keep_filters(self):
        app,root,errors=self.app();app.show_page(4);self.pump(app,.4);guide=app.guide_page;guide.variables['query'].set('Monza');self.pump(app,.25)
        app.root.focus_force();app.focus_search();self.pump(app,.05);self.assertIs(app.root.focus_get(),guide.search_entry)
        guide.search_field.clear();self.pump(app,.25);self.assertEqual(guide.state['query'],'');self.assertFalse(errors)
    def test_recent_video_result_passes_selected_curve_directly(self):
        from control_video_results import show
        app,root,errors=self.app();folder=root/'VideoCurves/result';folder.mkdir(parents=True)
        (folder/'curve.json').write_text(json.dumps(dict(format='stintrix.video-curves',version=1,identity=dict(track='Monza'),video_file='race.mp4',quality={},rows=[])),'utf-8');(folder/'report.html').write_text('report','utf-8')
        w=show(app,root);self.pump(app,.4);w.results_table.selection_set(w.results_table.get_children());self.pump(app,.05)
        with patch('control_video_history.show') as compare:w.results_buttons['history'].invoke();compare.assert_called_once_with(app,root,folder/'curve.json')
        self.assertFalse(errors)
    def test_pair_quick_selection_swap_and_incompatible_layout_are_inline(self):
        from control_lap_pair import show
        app,root,errors=self.app();records=[dict(folder=str(root/f'Logs/{i}'),key=f'Logs/{i}',track='Circuit',track_layout=str(i),track_length_m=5000,vehicle='BMW',date='2026-10-20',session_type='Race',status='complete') for i in range(2)]
        laps=[dict(number=1,time_s=100,track_length_m=5000),dict(number=2,time_s=98,track_length_m=5000)]
        with patch('control_lap_pair.inventory',return_value=records),patch('control_lap_pair.valid_laps',return_value=laps),patch('control_lap_pair.finished_metadata',side_effect=lambda folder:next(item for item in records if item['folder']==str(folder))),patch('control_lap_pair.export_pair') as export:
            w=show(app,root);self.pump(app,.5);c=w.pair_controls;self.assertTrue(c['compare'].enabled)
            c['quick']['A'].invoke();self.assertFalse(c['compare'].enabled);self.assertIn('不同圈',c['status'].get())
            c['numbers']['A'].set(next(iter(c['state']['laps']['A'])));c['refresh']();a=c['numbers']['A'].get();b=c['numbers']['B'].get();c['quick']['swap'].invoke();self.assertEqual((c['numbers']['A'].get(),c['numbers']['B'].get()),(b,a))
            c['events']['B'].set(list(c['state']['events'])[1]);c['scan']('B');self.pump(app,.4);self.assertFalse(c['compare'].enabled);c['compare'].invoke();export.assert_not_called()
        self.assertFalse(errors)
    def test_danger_defaults_to_cancel_and_labels_are_explicit(self):
        from control_danger import confirm
        app,root,errors=self.app();captured=[]
        def cancel():
            window=app.root._stintrix_danger;captured.append(window.danger_buttons['delete'].cget('text'));window.danger_buttons['cancel'].invoke()
        app.root.after(80,cancel);self.assertFalse(confirm(app.root,'删除赛事记录','永久删除选中的赛事记录？',['fixture'],warning='将从本机删除所选赛事的全部记录、圈文件与报告，无法恢复。'))
        self.assertEqual(captured,['永久删除']);self.assertIsNone(app.root.grab_current());self.assertFalse(errors)
