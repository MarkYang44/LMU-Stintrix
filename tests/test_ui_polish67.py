"""Auxiliary result workflows: explicit targets, bounded reads and honest failures."""
import json,os,threading,unittest
from pathlib import Path
from unittest.mock import patch
from tests import test_ui_efficiency as helpers
from tests import test_ui_polish56 as maintenance


def video(root,name,track='Fuji Speedway',reports=('raw',),quality=None):
    folder=root/'VideoCurves'/name;folder.mkdir(parents=True,exist_ok=True)
    value=dict(format='stintrix.video-curves',version=1,created_utc='20261025T001000Z',identity=dict(track=track),video_file=name+'.mp4',quality=quality or {},rows=[])
    (folder/'curve.json').write_text(json.dumps(value),'utf-8')
    for kind in reports:(folder/('report.html' if kind=='raw' else 'report_120hz.html')).write_text('fixture','utf-8')
    return str(folder)


class Rules(unittest.TestCase):
    def test_blank_exception_and_partial_details_remain_failed_and_continue(self):
        from control_batch import run_items
        events=[]
        def operation(value):
            if value==0:raise RuntimeError()
            return dict(errors=['  ']) if value==1 else dict(path='kept',errors=[])
        result=run_items(list(enumerate(range(3))),operation,threading.Event(),lambda *e:events.append(e))
        self.assertEqual(result[0],(0,None,'RuntimeError'));self.assertEqual(result[1][2],'未提供错误详情');self.assertEqual(result[2][2],'')
        self.assertEqual([e[1] for e in events if e[1]!='正在处理'],['失败','部分失败','已完成'])


@unittest.skipUnless(os.name=='nt','Native Tk')
class UI(unittest.TestCase):
    app=helpers.EfficiencyTests.app;pump=helpers.EfficiencyTests.pump
    def results(self,count=2):
        from control_video_results import show
        app,root,errors=self.app()
        for i in range(count):video(root,f'video-{i:02}',track='Monza' if i==0 else 'Fuji Speedway')
        w=show(app,root);w.geometry('760x500');self.pump(app,.35);return app,root,errors,w
    def test_batch_callback_and_copy_agree_with_failure_states_then_retry(self):
        from control_batch import start
        app,root,errors=self.app();received=[];retry=[False]
        def work(value):
            if retry[0] or value==2:return dict(value=value,errors=[])
            if value==0:raise RuntimeError()
            return dict(value=value,errors=[''])
        job=start(app,'赛事包导出任务',[0,1,2],work,on_done=received.append);self.pump(app,.4)
        self.assertEqual(job.states,['失败','部分失败','已完成']);self.assertEqual(set(job.results),{2});self.assertEqual([i['value'] for i in received[-1]['items']],[2]);self.assertEqual(len(received[-1]['errors']),2)
        with patch.object(job.table,'copy_text') as copied:job.copy_button.invoke();self.assertIn('RuntimeError',copied.call_args.args[0]);self.assertIn('未提供错误详情',copied.call_args.args[0])
        retry[0]=True;job.retry_button.invoke();self.pump(app,.4);self.assertEqual(job.states,['已完成']*3);self.assertEqual(set(job.results),{0,1,2});self.assertEqual(received[-1]['errors'],[]);self.assertFalse(errors)
    def test_multiselect_disables_and_guards_all_single_result_actions(self):
        app,root,errors,w=self.results();table=w.results_table;table.selection_set(table.get_children());self.pump(app,.05)
        self.assertIn('已选 2',w.results_count.get());self.assertIn('只选择一项',w.results_status.get());self.assertFalse(any(b.enabled for b in w.results_buttons.values()))
        with patch('control_video_results.os.startfile') as opener,patch('control_video_history.show') as history:
            for button in w.results_buttons.values():button.action()
            table.viewport.focus_set();table.viewport.event_generate('<Return>');self.pump(app,.05);opener.assert_not_called();history.assert_not_called()
        table.selection_set(());self.pump(app,.05);self.assertFalse(any(b.enabled for b in w.results_buttons.values()));self.assertFalse(errors)
    def test_single_result_availability_and_primary_action_match_reports(self):
        app,root,errors,w=self.results(0)
        raw=video(root,'raw',reports=('raw',),quality=dict(requested_sample_hz=30,actual_sample_hz=29.99));smooth=video(root,'smooth',reports=('smooth',));both=video(root,'both',reports=('raw','smooth'))
        w.refresh_results();self.pump(app,.35)
        for key,raw_on,smooth_on in [(raw,True,False),(smooth,False,True),(both,True,True)]:
            w.results_table.selection_set((key,));self.pump(app,.05);self.assertEqual(w.results_buttons['raw'].enabled,raw_on);self.assertEqual(w.results_buttons['smooth'].enabled,smooth_on);self.assertEqual('不增加原始精度' in w.results_status.get(),smooth_on)
        self.assertTrue(w.results_buttons['raw'].primary);w.results_table.selection_set((smooth,));self.pump(app,.05);w.focus_force();w.results_table.viewport.focus_set()
        with patch('control_video_results.os.startfile') as opener:w.results_table.viewport.event_generate('<Return>');self.pump(app,.05);opener.assert_called_once_with(str(Path(smooth)/'report_120hz.html'))
        self.assertFalse(errors)
    def test_multiple_selection_returns_after_filter_and_explicit_clear_stays_clear(self):
        app,root,errors,w=self.results();keys=w.results_table.get_children();w.results_table.selection_set(keys);self.pump(app,.05)
        w.results_search.set('missing');self.pump(app,.12);self.assertEqual(w.results_table.selection(),());w.results_search_field.clear();self.assertEqual(w.results_table.selection(),keys)
        w.results_table.selection_set(());self.pump(app,.05);w.refresh_results();self.pump(app,.3);self.assertEqual(w.results_table.selection(),());self.assertFalse(errors)
    def test_reopening_refreshes_new_results_and_preserves_query_selection_and_scroll(self):
        from control_video_results import show
        app,root,errors,w=self.results(18);w.results_search.set('video');self.pump(app,.12);keys=w.results_table.get_children()[7:9];w.results_table.selection_set(keys);self.pump(app,.05);w.results_table.scroller.move(160);self.pump(app,.05);offset=w.results_table.offset;xoffset=w.results_table.xoffset=55
        video(root,'video-new');self.assertIs(show(app,root),w);self.pump(app,.35)
        self.assertEqual(len(w.results_state['items']),19);self.assertEqual(w.results_search.get(),'video');self.assertEqual(w.results_table.selection(),keys);self.assertAlmostEqual(w.results_table.offset,offset);self.assertAlmostEqual(w.results_table.xoffset,xoffset);self.assertFalse(errors)
    def test_repeated_refreshes_have_one_reader_and_one_latest_pending_request(self):
        import video_results
        from control_video_results import show
        app,root,errors,w=self.results();gate=threading.Event();entered=threading.Event();calls=[];active=[0,0]
        def read(path):
            calls.append(path);active[0]+=1;active[1]=max(active)
            try:
                if len(calls)==1:entered.set();gate.wait(3)
                return video_results.inventory(path)
            finally:active[0]-=1
        try:
            with patch('control_video_results.inventory',side_effect=read):
                w.refresh_results();self.assertTrue(entered.wait(1))
                for _ in range(6):show(app,root)
                self.pump(app,.05);self.assertEqual(len(calls),1);self.assertTrue(w.results_state['pending']);gate.set();self.pump(app,.5);self.assertEqual(len(calls),2)
        finally:gate.set()
        self.assertEqual(active[1],1);self.assertFalse(w.results_state['loading']);self.assertFalse(w.results_state['pending']);self.assertFalse(errors)
    def test_refresh_error_preserves_cached_context_and_f5_recovers(self):
        app,root,errors,w=self.results();keys=w.results_table.get_children();w.results_table.selection_set(keys);self.pump(app,.05)
        with patch('control_video_results.inventory',side_effect=RuntimeError()):w.refresh_results();self.pump(app,.3)
        self.assertIn('RuntimeError',w.results_status.get());self.assertEqual(w.results_table.selection(),keys);self.assertEqual(len(w.results_state['items']),2)
        video(root,'third');w.focus_force();self.pump(app,.05);w.event_generate('<F5>');self.pump(app,.3);self.assertEqual(len(w.results_state['items']),3);self.assertIsNone(w.results_state['error']);self.assertEqual(w.results_table.selection(),keys);self.assertFalse(errors)
    def test_closed_results_ignore_old_reader_and_pending_search_callbacks(self):
        import video_results
        from control_video_results import show
        app,root,errors,w=self.results();gate=threading.Event();entered=threading.Event()
        def read(path):entered.set();gate.wait(3);return video_results.inventory(path)
        try:
            with patch('control_video_results.inventory',side_effect=read):w.refresh_results();self.assertTrue(entered.wait(1));w.results_search.set('missing');w.destroy();gate.set();self.pump(app,.3)
        finally:gate.set()
        new=show(app,root);self.pump(app,.3);self.assertEqual(len(new.results_table.get_children()),2);self.assertFalse(errors)
    def test_video_search_merges_input_enter_and_clear_are_immediate(self):
        app,root,errors,w=self.results()
        with patch.object(w.results_table,'replace',wraps=w.results_table.replace) as replaced:
            for query in ('v','vi','vid','vide','video','video-'):w.results_search.set(query)
            self.pump(app,.13);self.assertEqual(replaced.call_count,1)
            w.focus_force();w.results_search_field.entry.focus_set();self.pump(app,.03);w.results_search.set('missing');w.results_search_field.entry.event_generate('<Return>');self.pump(app,.01);self.assertEqual(len(w.results_table.get_children()),0)
            w.results_search_field.clear();self.assertEqual(len(w.results_table.get_children()),2)
        self.assertFalse(errors)
    def test_video_language_theme_keep_multiple_selection_and_translated_summary(self):
        import i18n
        app,root,errors,w=self.results();keys=w.results_table.get_children();w.results_table.selection_set(keys);self.pump(app,.05);app.set_theme('light');app.toggle_language();self.pump(app,.15)
        self.assertEqual(w.results_table.selection(),keys);self.assertEqual(w.results_table.labels['video'],i18n.tr('视频文件'));self.assertIn('selected',w.results_count.get());self.assertIn('Select one',w.results_status.get());self.assertFalse(any(b.enabled for b in w.results_buttons.values()));self.assertFalse(errors)
    def test_worklist_language_retranslates_original_headers_without_resetting_context(self):
        import i18n
        from control_cache_panel import show
        app,root,errors=self.app();w=show(app);self.pump(app,.3);v=w.worklist;v.view.set('clearable');v.render();v.table.selection_set(('catalog',));self.pump(app,.05);v.table.widths['name']=233.125;v.table.schedule();app.toggle_language();self.pump(app,.15)
        self.assertEqual(v.table.labels,dict(name='Contents',size='Size / MiB',files='Files',kind='Action'));self.assertEqual(v.table.selection(),('catalog',));self.assertEqual(v.view.get(),'clearable');self.assertEqual(v.table.widths['name'],233.125)
        v.view.set('all');v.render();self.assertEqual(v.table.rows['video'][0],'Video extraction results (retained)');app.toggle_language();self.pump(app,.1);self.assertEqual(v.table.labels['name'],'内容');self.assertEqual(v.table.rows['video'][0],'视频提取结果（保留）');self.assertFalse(errors)
    def test_worklist_search_merges_input_and_clear_restores_selection(self):
        from control_cache_panel import show
        app,root,errors=self.app();w=show(app);self.pump(app,.3);v=w.worklist;v.table.selection_set(('catalog',));self.pump(app,.05)
        with patch.object(v.table,'replace',wraps=v.table.replace) as replaced:
            for query in ('m','mi','mis','miss','missi','missing'):v.query.set(query)
            self.pump(app,.13);self.assertEqual(replaced.call_count,1);self.assertEqual(v.table.selection(),());v.search.clear();self.assertEqual(v.table.selection(),('catalog',))
            w.focus_force();v.search.entry.focus_set();self.pump(app,.03);v.query.set('missing');v.search.entry.event_generate('<Return>');self.pump(app,.01);self.assertEqual(v.table.selection(),())
        self.assertFalse(errors)
    def test_worklist_refresh_preserves_scroll_selection_filter_and_query(self):
        from control_worklist import WorkList
        app,root,errors=self.app();v=WorkList(app,'报告任务与分步重试',[('value','内容',200)],lambda x:str(x),lambda x:(str(x),),filters=dict(all='全部报告'));v.window.geometry('800x620');v.load(lambda:list(range(30)),'就绪');self.pump(app,.3);v.query.set('');v.table.selection_set(('15',));v.table.scroller.move(200);self.pump(app,.05);offset=v.table.offset
        v.load(lambda:list(range(31)),'就绪');self.pump(app,.3);self.assertEqual(v.table.selection(),('15',));self.assertAlmostEqual(v.table.offset,offset);self.assertEqual(v.view.get(),'all');v.query.set('pending callback');v.window.destroy();self.pump(app,.15);self.assertFalse(errors)
    def retry(self,app,root,partial=False):
        from control_report_tasks import show
        from report_state import save,STEPS
        folder=maintenance.session(root,'retry');(folder/'review.html').write_text('fixture');w=show(app);self.pump(app,.3);v=w.worklist;v.table.selection_set((str(folder),));self.pump(app,.05)
        def work(*_):save(folder,{key:dict(state='error' if partial and key=='images' else 'ready',error='fixture' if partial and key=='images' else '') for key in STEPS})
        with patch('report_worker.run',side_effect=work):v.buttons['retry'].invoke();self.pump(app,.5)
        job=app.report_retry_job;job.table.selection_set(('0',));self.pump(app,.05);return folder,v,job
    def test_report_success_keeps_direct_result_actions_after_leaving_pending_list(self):
        app,root,errors=self.app();folder,v,job=self.retry(app,root);self.assertEqual(v.table.get_children(),());self.assertIsNotNone(job.result_actions);self.assertTrue(all(b.enabled for b in job.result_actions.buttons.values()));self.assertIn(str(folder),job.result_actions.path.get())
        with patch('control_batch_results.os.startfile') as opener:job.result_actions.buttons['review'].invoke();opener.assert_called_once_with(str(folder/'review.html'))
        with patch('control_session_location.locate',return_value=True) as locate:job.result_actions.buttons['locate'].invoke();locate.assert_called_once_with(app,folder);self.assertEqual(job.window.state(),'withdrawn')
        self.assertFalse(errors)
    def test_report_partial_result_keeps_folder_and_ready_review_without_regeneration(self):
        app,root,errors=self.app();folder,v,job=self.retry(app,root,True);self.assertEqual(job.states,['部分失败']);self.assertEqual(v.table.get_children(),(str(folder),));self.assertTrue(job.retry_button.enabled);self.assertTrue(job.result_actions.buttons['review'].enabled)
        self.assertNotIn('\n',job.table.rows['0'][2]);self.assertIn('\n',job.errors[0])
        with patch.object(job.table,'copy_text') as copied:job.copy_button.invoke();self.assertIn(job.errors[0],copied.call_args.args[0])
        original=(folder/'inputs.csv').read_bytes()
        with patch('report_worker.run') as generate,patch('control_batch_results.os.startfile') as opener:job.result_actions.buttons['folder'].invoke();job.result_actions.buttons['review'].invoke();self.assertEqual(opener.call_count,2);generate.assert_not_called()
        self.assertEqual((folder/'inputs.csv').read_bytes(),original);self.assertFalse(errors)
    def test_result_readiness_rechecks_missing_and_malformed_receipts(self):
        app,root,errors=self.app();folder,v,job=self.retry(app,root);actions=job.result_actions
        for steps in ([],dict(review=[]),dict(review=dict(state='error'))):
            (folder/'report_status.json').write_text(json.dumps(dict(version=2,steps=steps)));actions.sync();self.assertFalse(actions.buttons['review'].enabled);self.assertTrue(actions.buttons['folder'].enabled)
        (folder/'review.html').unlink();actions.sync();self.assertFalse(actions.open_review());self.assertFalse(errors)
