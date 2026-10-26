"""Renderer draft exit, save scope, result handoff and reversible table layouts."""
import json,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,Mock
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from tests import test_ui_efficiency as helpers


class Rules(unittest.TestCase):
    def test_renderer_save_keeps_unknown_fields_and_refuses_corrupt_settings(self):
        import renderer_config
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as temp:
            root=Path(temp);p=root/'renderer_settings.json';p.write_text(json.dumps({'custom':{'keep':17}}));renderer_config.save(dict(mode='native',executable=''),root)
            self.assertEqual(json.loads(p.read_text())['custom'],{'keep':17})
            for invalid in ('broken','[]'):
                p.write_text(invalid)
                with self.assertRaises(ValueError):renderer_config.save(dict(mode='native',executable=''),root)
                self.assertEqual(p.read_text(),invalid)
    def test_native_report_exception_retains_imported_output_and_retry_avoids_reimport(self):
        import control_transfers
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as temp:
            root=Path(temp);source=root/'source.duckdb';source.write_bytes(b'fixture');folder=root/'output';folder.mkdir();app=SimpleNamespace(root=None,data_path=root,refresh=Mock())
            with patch('control_transfers.filedialog.askopenfilenames',return_value=[str(source)]),patch('control_transfers.start') as start,patch('telemetry_import.import_recording',return_value=folder) as imported,patch('session_reports.make_report',side_effect=[RuntimeError(),{'state':'ready'}]):
                control_transfers.import_native(app);self.assertTrue(start.call_args.kwargs['result_actions']);operation=start.call_args.args[3]
                failed=operation(str(source));self.assertEqual(failed['errors'],['RuntimeError']);self.assertEqual(failed['path'],str(folder));self.assertFalse(operation(str(source))['errors']);self.assertEqual(imported.call_count,1)


@unittest.skipUnless(os.name=='nt','Native Tk')
class UI(unittest.TestCase):
    app=helpers.EfficiencyTests.app;pump=helpers.EfficiencyTests.pump
    def mount(self,app,page=3,section='renderer'):
        app.show_page(page);self.pump(app,.3)
        if page==3:app.data_tasks.select(section);self.pump(app,.08)
    def renderer(self):
        app,root,errors=self.app();self.mount(app);app.renderer_mode.set('native');app.renderer_path.set('D:/fixture renderer/Image Generate.exe');return app,root,errors
    def batch(self,app,root,partial=False):
        from control_batch import start
        folder=root/'ImportedLogs/result';folder.mkdir(parents=True,exist_ok=True)
        (folder/'session.json').write_text(json.dumps(dict(status='complete',track='Fuji Speedway',vehicle='BMW',session=10,started_utc='2026-10-24T12:00:00+00:00')))
        (folder/'review.html').write_text('<html>fixture</html>');(folder/'report_status.json').write_text(json.dumps(dict(version=2,steps={'review':{'state':'ready'}})))
        job=start(app,'官方遥测导入任务',['one.duckdb','two.duckdb'],lambda _:dict(path=str(folder),errors=['fixture'] if partial else []),result_actions=True);self.pump(app,.35);job.table.selection_set(('0',));return job,folder
    def test_anchor_updates_scope_and_other_dirty_module_can_be_selected_explicitly(self):
        from control_video_widgets import Action
        app,root,errors=self.app();self.mount(app,2);forms=app.pages.pages[2].forms;forms['sampling']['fixed_hz'].set('240');field=app.form_panels['vehicle'].form_feedback.fields['reserve_l'][0].entry;app.root.focus_force();field.focus_set();self.pump(app,.08)
        def walk(w):
            for child in w.winfo_children():yield child;yield from walk(child)
        anchor=next(w for w in walk(app.shell.action_host) if isinstance(w,Action) and w.label=='输入采样');anchor.invoke();self.assertEqual(app.form_bar.current,'sampling');self.assertTrue(app.form_bar.save.enabled)
        forms['vehicle']['reserve_l'].set('4');self.assertIn('另有',app.form_bar.message.get());app.form_bar.choice.set('vehicle');app.form_bar.selector.event_generate('<<ComboboxSelected>>');self.assertEqual(app.form_bar.current,'vehicle');self.assertTrue(app.form_bar.save.enabled)
        forms['sampling']['fixed_hz'].set('120');forms['vehicle']['reserve_l'].set('0.0');self.assertFalse(errors)
    def test_scope_and_multiple_drafts_survive_language_theme_and_return(self):
        app,root,errors=self.app();self.mount(app,2);forms=app.pages.pages[2].forms;forms['sampling']['fixed_hz'].set('240');forms['vehicle']['reserve_l'].set('4');app.form_bar.select('vehicle');app.show_page(0);app.show_page(2);self.pump(app,.15);self.assertEqual(app.form_bar.current,'vehicle')
        app.set_theme('light');app.toggle_language();self.pump(app,.2);self.assertEqual(app.form_bar.current,'vehicle');self.assertTrue(app.form_bar.save.enabled);self.assertIn('1',app.form_bar.selector.labels['sampling']);self.assertFalse(errors)
    def test_renderer_cancel_exit_retains_draft_after_leaving_data_page(self):
        app,root,errors=self.renderer();app.show_page(0)
        with patch('control_confirm.ask',return_value='cancel') as ask,patch.object(app,'close') as close:app.request_close();ask.assert_called_once();close.assert_not_called()
        self.mount(app);self.assertEqual(app.renderer_path.get(),'D:/fixture renderer/Image Generate.exe');self.assertFalse((root/'renderer_settings.json').exists());self.assertFalse(errors)
    def test_renderer_discard_exit_continues_without_writing_draft(self):
        app,root,errors=self.renderer();app.show_page(0)
        with patch('control_confirm.ask',return_value='discard'),patch.object(app,'close') as close:app.request_close();close.assert_called_once()
        self.assertIsNone(app.renderer_draft);self.mount(app);self.assertEqual(app.renderer_path.get(),'');self.assertFalse((root/'renderer_settings.json').exists());self.assertFalse(errors)
    def test_renderer_save_exit_from_other_page_preserves_unknown_and_clears_baseline(self):
        app,root,errors=self.app();p=root/'renderer_settings.json';p.write_text(json.dumps(dict(mode='racecom',executable='',custom=777)));self.mount(app);app.renderer_mode.set('native');app.renderer_path.set('D:/fixture renderer/Image Generate.exe');app.show_page(0)
        with patch('control_confirm.ask',return_value='save'),patch.object(app,'close') as close:app.request_close();close.assert_called_once()
        self.assertEqual(json.loads(p.read_text())['custom'],777);self.assertIsNone(app.renderer_draft);self.assertEqual(app.renderer_baseline['renderer_path'],app.renderer_path.get());self.assertFalse(app.renderer_editor.button.enabled)
        with patch('control_confirm.ask') as ask,patch.object(app,'close') as close:app.request_close();ask.assert_not_called();close.assert_called_once()
        self.assertFalse(errors)
    def test_invalid_renderer_exit_save_keeps_form_and_blocks_close(self):
        app,root,errors=self.renderer();app.renderer_mode.set('racecom');app.show_page(0)
        with patch('control_confirm.ask',return_value='save'),patch.object(app,'close') as close:app.request_close();close.assert_not_called()
        self.assertEqual(app.data_tasks.current,'renderer');self.assertTrue(app.renderer_draft);self.assertIn('未保存',app.renderer_editor.status.get());self.assertFalse((root/'renderer_settings.json').exists());self.assertFalse(errors)
    def test_renderer_write_failure_keeps_file_and_draft_then_save_succeeds(self):
        app,root,errors=self.renderer();editor=app.renderer_editor
        with patch('renderer_config.atomic_json',side_effect=OSError('fixture denied')):self.assertFalse(editor.save())
        self.assertTrue(app.renderer_draft);self.assertFalse((root/'renderer_settings.json').exists());self.assertIn('fixture denied',editor.status.get());self.assertTrue(editor.save());self.assertIsNone(app.renderer_draft)
        app.show_page(0);self.mount(app);app.set_theme('light');app.toggle_language();self.pump(app,.15);self.assertIsNone(app.renderer_draft);self.assertFalse(app.renderer_editor.button.enabled);self.assertFalse(errors)
    def test_renderer_ctrl_s_has_one_live_binding_after_rebuild(self):
        app,root,errors=self.renderer();app.set_theme('light');app.toggle_language();self.pump(app,.15);app.root.focus_force();app.renderer_editor.path.entry.focus_set();self.pump(app,.05)
        import renderer_config
        with patch('renderer_config.save',wraps=renderer_config.save) as saved:app.renderer_editor.path.entry.event_generate('<Control-s>');self.pump(app,.1);self.assertEqual(saved.call_count,1)
        self.assertIsNone(app.renderer_draft);self.assertFalse(errors)
    def test_storage_summary_is_collapsed_complete_and_no_duplicate_export_buttons(self):
        app,root,errors=self.app(True);self.mount(app,3,'storage');b=app.data_browser;b.table.selection_set(b.table.get_children());b.sync();self.pump(app,.1)
        self.assertFalse(b.details.body.winfo_manager());self.assertEqual(b.count.get(),'已选 8 场赛事');self.assertEqual(len(b.selection_text.get('1.0','end-1c').splitlines()),9);self.assertEqual(set(app.storage_buttons),{'compress','columnar','restore'})
        visible=(app.scroll.winfo_rooty()+app.scroll.winfo_height()-b.table.viewport.winfo_rooty())/b.table.rowheight;self.assertGreaterEqual(visible,3);b.details.set_open(True);self.assertTrue(b.details.body.winfo_manager());self.assertFalse(errors)
    def test_storage_picker_label_tracks_state_in_both_languages_and_keeps_selection(self):
        app,root,errors=self.app(True);self.mount(app,3,'storage');b=app.data_browser;b.table.selection_set(b.table.get_children()[:2]);self.assertEqual(b.toolbar['picker'].cget('text'),'收起赛事列表');b.toolbar['picker'].invoke();self.assertFalse(b.picker_open);self.assertEqual(b.toolbar['picker'].cget('text'),'选择赛事')
        app.toggle_language();self.pump(app,.15);b=app.data_browser;self.assertEqual(len(b.selected()),2);self.assertEqual(b.toolbar['picker'].cget('text'),'Select sessions');b.toolbar['picker'].invoke();self.assertEqual(b.toolbar['picker'].cget('text'),'Hide session list');self.assertFalse(errors)
    def test_default_compact_columns_keep_lap_and_car_visible_without_saving_preferences(self):
        app,root,errors=self.app(True);self.mount(app,1);table=app.tree;positions={k:x for k,x,_ in table.positions()}
        for key in ('lap','car'):self.assertLessEqual(positions[key]+table.actual[key],table.viewport.winfo_width())
        self.assertFalse((root/'table_views.json').exists());self.assertFalse(errors)
    def test_existing_custom_layout_is_retained_and_presets_restore_exact_widths(self):
        app,root,errors=self.app(True);p=root/'table_views.json';custom=dict(visible=['car','date','lap'],frozen=['date'],widths={'date':233.125,'car':211,'lap':97},custom='keep');p.write_text(json.dumps(dict(version=1,tables={'review':custom},unknown=42)));self.mount(app,1);table=app.tree;self.assertEqual(table.displaycolumns,custom['visible']);self.assertEqual(table.widths['date'],233.125)
        table.selection_set(table.get_children()[:2]);chosen=table.selection();self.assertTrue(table.apply_layout_preset('compact'));self.assertTrue(table.apply_layout_preset('previous'));self.assertEqual(table.displaycolumns,custom['visible']);self.assertEqual(table.widths['date'],233.125);self.assertEqual(table.selection(),chosen);saved=json.loads(p.read_text());self.assertEqual(saved['unknown'],42);self.assertEqual(saved['tables']['review']['custom'],'keep');self.assertFalse(errors)
    def test_preset_save_failure_keeps_current_view_and_previous_custom_values(self):
        app,root,errors=self.app(True);self.mount(app,1);table=app.tree;before=(list(table.displaycolumns),dict(table.widths));self.assertTrue(table.apply_layout_preset('full'));p=root/'table_views.json';content=p.read_bytes();view=list(table.displaycolumns)
        with patch('control_table_preferences.atomic_json',side_effect=OSError('fixture denied')):self.assertFalse(table.apply_layout_preset('compact'))
        self.assertEqual(table.displaycolumns,view);self.assertEqual(p.read_bytes(),content);self.assertIn('fixture denied',app.status.get());self.assertFalse(errors)
    def test_manual_column_save_keeps_compact_order_and_complete_fields_remain_available(self):
        app,root,errors=self.app(True);self.mount(app,1);table=app.tree;order=list(table.displaycolumns);w=table.show_columns();w.column_visible['result'].set(False);self.assertTrue(w.column_save());self.assertEqual(table.displaycolumns,[k for k in order if k!='result']);w.column_close();self.assertTrue(table.apply_layout_preset('full'));self.assertEqual(set(table.displaycolumns),set(table.columns));self.assertFalse(errors)
    def test_repeating_same_preset_keeps_the_previous_layout_available(self):
        app,root,errors=self.app(True);self.mount(app,1);table=app.tree;original=list(table.displaycolumns);table.apply_layout_preset('full');before=(root/'table_views.json').read_bytes();table.apply_layout_preset('full');self.assertEqual((root/'table_views.json').read_bytes(),before);table.apply_layout_preset('previous');self.assertEqual(table.displaycolumns,original);self.assertFalse(errors)
    def test_batch_ready_result_actions_open_existing_files_and_partial_output_remains_accessible(self):
        app,root,errors=self.app();job,folder=self.batch(app,root,True);self.assertTrue(job.result_actions.buttons['folder'].enabled);self.assertTrue(job.result_actions.buttons['review'].enabled)
        with patch('control_batch_results.os.startfile') as opened:job.result_actions.open_folder();job.result_actions.open_review();self.assertEqual([c.args[0] for c in opened.call_args_list],[str(folder),str(folder/'review.html')])
        self.assertEqual(job.states,['部分失败','部分失败']);self.assertFalse(errors)
    def test_batch_review_readiness_is_rechecked_and_missing_or_multiple_selection_disables_actions(self):
        app,root,errors=self.app();job,folder=self.batch(app,root);view=job.result_actions;(folder/'report_status.json').write_text(json.dumps(dict(version=2,steps={'review':{'state':'pending'}})));view.sync();self.assertFalse(view.buttons['review'].enabled);self.assertTrue(view.buttons['folder'].enabled)
        (folder/'report_status.json').write_text(json.dumps(dict(version=2,steps={'review':{'state':'ready'}})));view.sync();self.assertTrue(view.buttons['review'].enabled);(folder/'review.html').unlink()
        with patch('control_batch_results.os.startfile') as opened:self.assertFalse(view.open_review());opened.assert_not_called()
        job.table.selection_set(('0','1'));self.assertTrue(all(not b.enabled for b in view.buttons.values()));self.assertFalse(errors)
    def test_batch_busy_results_cannot_open(self):
        app,root,errors=self.app();job,folder=self.batch(app,root);job.busy=True;job.result_actions.sync()
        with patch('control_batch_results.os.startfile') as opened:self.assertFalse(job.result_actions.open_folder());opened.assert_not_called()
        job.busy=False;self.assertFalse(errors)
    def test_batch_search_coalesces_edits_and_clear_is_immediate_without_changing_retry_scope(self):
        app,root,errors=self.app();job,folder=self.batch(app,root,True)
        with patch.object(job.table,'replace',wraps=job.table.replace) as replaced:
            for query in ('o','on','one','one.','one.d','one.du'):job.query.set(query)
            self.pump(app,.15);self.assertEqual(replaced.call_count,1);job.search_field.clear();self.assertEqual(replaced.call_count,2);self.pump(app,.12);self.assertEqual(replaced.call_count,2)
        self.assertEqual(job.states,['部分失败','部分失败']);self.assertFalse(errors)
    def test_locate_outside_filter_keeps_query_and_restores_original_selection(self):
        from control_session_location import locate
        app,root,errors=self.app(True);self.mount(app,1);target=next(e for e in app.items if 'Spa' in e['track']);app.search.set('Fuji');app.populate();original=app.tree.get_children()[0];app.tree.selection_set((original,));identity=app.items[int(original)]['folder'];state=dict(app.review_filters.state)
        self.assertTrue(locate(app,target['folder']));self.pump(app,.35);self.assertEqual(app.search.get(),'Fuji');self.assertEqual(app.review_filters.state,state);self.assertEqual(app.items[int(app.tree.selection()[0])]['folder'],target['folder']);self.assertIn('筛选外',app.session_locator.label.cget('text'));app.session_locator.restore();self.assertEqual(app.items[int(app.tree.selection()[0])]['folder'],identity);self.assertEqual(app.search.get(),'Fuji');self.assertIsNone(app.session_location);self.assertFalse(errors)
    def test_query_edit_ends_temporary_reveal_and_unknown_target_never_changes_page(self):
        from control_session_location import locate
        app,root,errors=self.app(True);self.mount(app,1);target=app.items[0]['folder'];locate(app,target);self.pump(app,.3);app.search.set('missing');app.populate();self.assertIsNone(app.session_location);self.assertFalse(app.tree.selection());page=app.page;self.assertFalse(locate(app,root/'not-a-session'));self.assertEqual(app.page,page);self.assertFalse(errors)
    def test_batch_locate_hides_task_window_and_selects_its_exact_session(self):
        app,root,errors=self.app();job,folder=self.batch(app,root);self.assertTrue(job.result_actions.locate());self.pump(app,.35);self.assertEqual(app.page,1);self.assertEqual(Path(app.items[int(app.tree.selection()[0])]['folder']),folder);self.assertFalse(job.window.winfo_viewable());self.assertFalse(errors)
