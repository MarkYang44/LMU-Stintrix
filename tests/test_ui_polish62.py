"""Navigation, context, import ordering and reusable record-curve exports."""
import json,os,sys,tempfile,unittest
from pathlib import Path
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from tests import test_ui_efficiency as helpers
from tests.test_record_intelligence import entry
from tests.test_career_analysis import XML,driver


def histories(root,count=12):
    values=[]
    for i in range(count):
        e=entry(100-i*.1,f'2026-10-{i+1:02d}T10:00:00Z');folder=Path(root)/'Logs'/('history'+str(i));folder.mkdir(parents=True,exist_ok=True);file=folder/'lap.json';file.write_text('{}')
        e.update(folder=str(folder),file=str(file),observed_utc=e['session']['started_utc'],improvement_s=.1 if i else None);values.append(e)
    return dict(entries=values,missing_dates=0,conflicts=0)


def official(root,count=12):
    from official_results import parse
    source=Path(root)/'fixture-results';source.mkdir(parents=True,exist_ok=True);file=source/'race.xml';file.write_text(XML.format(drivers=driver()),encoding='utf-8');e=parse(file)[0];values=[]
    for i in range(count):
        v=deepcopy(e);v.update(id=f'{i:024x}',started_utc=f'2026-10-{i+1:02d}T10:00:00Z',link_status='unmatched',linked_folder=None,position_conflicts={},match_candidates=[],folder=str(Path(root)/'OfficialResults/events'/str(i)));values.append(v)
    return dict(version=1,entries=values,errors=[],conflicts=[],source_directory=str(source))


class Rules(unittest.TestCase):
    def test_curve_identity_tracks_source_change_not_object_identity(self):
        from control_record_browser import curve_identity
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as tmp:
            e=histories(tmp,1)['entries'][0];a=curve_identity(e);self.assertEqual(a,curve_identity(deepcopy(e)));Path(e['file']).write_text('source changed');self.assertNotEqual(a,curve_identity(e))
    def test_real_curve_exports_use_unique_paths_and_preserve_source_and_previous_output(self):
        from tests.test_personal_records import FeatureTests,TEMPLATE
        from laps import export_fastest
        from personal_records import records
        from control_record_browser import save_curve
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as tmp:
            folder=FeatureTests().session(tmp,'fixture');export_fastest(folder,TEMPLATE);e=records(tmp)[0];before={p:p.read_bytes() for p in folder.rglob('*') if p.is_file()};one=Path(save_curve(tmp,e));saved=one.read_bytes();two=Path(save_curve(tmp,e))
            self.assertNotEqual(one,two);self.assertEqual(one.read_bytes(),saved);self.assertIn('<canvas',two.read_text('utf-8'));self.assertIn('stintrix-laps',two.read_text('utf-8'));self.assertEqual({p:p.read_bytes() for p in before},before)


@unittest.skipUnless(os.name=='nt','Native Tk')
class UI(unittest.TestCase):
    app=helpers.EfficiencyTests.app;pump=helpers.EfficiencyTests.pump
    def mount(self,app,root,kind='history',value=None):
        module='control_history.read_history' if kind=='history' else 'control_official_results.read_results';value=value or (histories(root) if kind=='history' else official(root))
        with patch(module,return_value=value):app.personal_record_view=kind;app.show_page(6);self.pump(app,.3)
        return app.record_loaders[kind].page,value
    def tab(self,app,title):
        def widgets(w):
            yield w
            for c in w.winfo_children():yield from widgets(c)
        next(w for w in widgets(app.content) if getattr(w,'label',None)==title and hasattr(w,'invoke')).invoke();self.pump(app,.2)
    def test_both_readers_show_rows_and_empty_actions_disable_when_search_hides_all(self):
        app,root,errors=self.app()
        for kind in ('history','official'):
            p,value=self.mount(app,root,kind);self.assertEqual(len(p.table.rows),12);self.assertIsNotNone(p.selected);p.query.set('no matching fixture');self.pump(app,.05);self.assertEqual(p.table.selection(),());self.assertFalse(p.buttons['note'].enabled);self.assertFalse(p.buttons['curve' if kind=='history' else 'xml'].enabled);app.focus_search();self.pump(app,.05);self.assertEqual(app.root.focus_get(),app.search_target.entry);app.search_target.clear();self.assertEqual(len(p.table.rows),12)
        self.assertFalse(errors)
    def test_refresh_reorder_keeps_record_selection_and_table_scroll(self):
        app,root,errors=self.app()
        for kind in ('history','official'):
            p,value=self.mount(app,root,kind);p.table.selection_set((p.table.order[8],));identity=p.identity(p.selected);p.table.set_offset(150);p.table.xoffset=90;offset=p.table.offset
            changed=dict(value,entries=list(reversed(value['entries'])));module='control_history.read_history' if kind=='history' else 'control_official_results.read_results'
            with patch.object(p.loader,'reader',new=lambda:changed):p.loader.read();self.pump(app,.25)
            self.assertEqual(p.entries if isinstance(p.entries,list) else list(p.entries.values()),changed['entries']);self.assertEqual(p.identity(p.selected),identity);self.assertEqual(p.table.offset,offset);self.assertEqual(p.table.xoffset,90)
        self.assertFalse(errors)
    def test_sibling_switch_releases_variables_and_return_restores_context(self):
        app,root,errors=self.app();p,value=self.mount(app,root);p.query.set('BMW');p.table.selection_set((p.table.order[7],));identity=p.identity(p.selected);p.table.set_offset(100);variables=list(p.variables.values())
        with patch('control_official_results.read_results',return_value=official(root)):self.tab(app,'官方战绩')
        self.assertTrue(p.disposed);self.assertIsNone(app.record_loaders['history'].page);self.assertTrue(all(v._tk is None for v in variables))
        with patch('control_history.read_history',return_value=value):self.tab(app,'纪录履历')
        current=app.record_loaders['history'].page;self.assertEqual(current.query.get(),'BMW');self.assertEqual(current.identity(current.selected),identity);self.assertEqual(current.table.offset,100);self.assertFalse(errors)
        variables=list(current.variables.values())
        try:
            app.close()
            try:self.pump(app,.1)
            except __import__('tkinter').TclError:pass
            self.assertTrue(current.disposed);self.assertTrue(all(v._tk is None for v in variables));self.assertFalse(errors)
        finally:
            try:gone=not app.root.winfo_exists()
            except __import__('tkinter').TclError:gone=True
            if gone:app.close=lambda:None
    def test_official_loading_blocks_sync_and_new_page_attaches_to_running_import(self):
        app,root,errors=self.app();p,value=self.mount(app,root,'official');jobs=[]
        with patch.object(app,'run_background',side_effect=lambda work,done:jobs.append((work,done))):
            p.sync_folder(value['source_directory']);self.assertEqual(p.driver_field.entry.cget('state'),'disabled');p.sync_folder(value['source_directory']);self.assertEqual(len(jobs),1)
            app.show_page(0);self.pump(app,.05);app.personal_record_view='official';app.show_page(6);self.pump(app,.05);current=app.record_loaders['official'].page;self.assertIsNot(current,p);self.assertEqual(len(jobs),1);self.assertFalse(current.buttons['sync'].enabled);jobs[0][1](dict(value,entries=value['entries'][:3]),None)
        self.assertEqual(len(current.table.rows),3);self.assertTrue(current.buttons['sync'].enabled);self.assertEqual(current.driver_field.entry.cget('state'),'normal');self.assertFalse(errors)
    def test_initial_read_late_error_after_navigation_never_touches_destroyed_tk(self):
        app,root,errors=self.app();jobs=[]
        with patch.object(app,'run_background',side_effect=lambda work,done:jobs.append(done)):
            app.personal_record_view='official';app.show_page(6);self.pump(app,.05);p=app.record_loaders['official'].page;app.show_page(0);self.pump(app,.05);jobs[0](None,'read fixture')
        self.assertTrue(p.disposed);self.assertIn('read fixture',app.status.get());self.assertFalse(errors)
    def test_queued_annotation_reload_runs_after_import_once(self):
        app,root,errors=self.app();p,value=self.mount(app,root,'official');jobs=[]
        with patch.object(app,'run_background',side_effect=lambda work,done:jobs.append(done)):
            p.sync_folder(value['source_directory']);p.loader.read(True);p.loader.read(True);self.assertEqual(len(jobs),1);jobs[0](value,None);self.assertEqual(len(jobs),2);self.assertTrue(p.loader.running);jobs[1](value,None)
        self.assertFalse(p.loader.running);self.assertFalse(errors)
    def test_load_failure_keeps_existing_rows_and_retry_restores_feedback(self):
        app,root,errors=self.app()
        for kind in ('history','official'):
            p,value=self.mount(app,root,kind);rows=dict(p.table.rows);module='control_history.read_history' if kind=='history' else 'control_official_results.read_results'
            with patch.object(p.loader,'reader',new=lambda:(_ for _ in ()).throw(OSError('read fixture'))):p.loader.read();self.pump(app,.25)
            self.assertEqual(p.table.rows,rows);self.assertIn('read fixture',p.status.get());self.assertTrue(p.buttons['refresh'].enabled)
            with patch.object(p.loader,'reader',new=lambda:value):p.loader.read();self.pump(app,.25)
            self.assertNotIn('read fixture',p.status.get())
        self.assertFalse(errors)
    def test_official_missing_game_offers_folder_and_sync_captures_driver(self):
        app,root,errors=self.app();p,value=self.mount(app,root,'official');p.driver.set('  Fixture Driver  ');jobs=[]
        with patch('paths.discover_game',return_value=None),patch('tkinter.filedialog.askdirectory',return_value=value['source_directory']),patch.object(app,'run_background',side_effect=lambda work,done:jobs.append(work)):
            p.sync_game()
        self.assertEqual(jobs[0].args[-1],'Fixture Driver');self.assertFalse(p.buttons['folder'].enabled);self.assertFalse(errors)
    def test_official_primary_opens_linked_review_then_xml_and_conflicts_remain_blocked(self):
        app,root,errors=self.app();p,value=self.mount(app,root,'official');e=p.selected;folder=root/'linked';folder.mkdir();(folder/'review.html').write_text('fixture');e.update(link_status='matched',linked_folder=str(folder));p.choose()
        with patch('control_record_browser.os.startfile') as opened:p.primary();opened.assert_called_once_with(str(folder/'review.html'))
        e['link_status']='conflict';p.choose();self.assertFalse(p.buttons['review'].enabled)
        with patch('control_record_browser.os.startfile') as opened:p.primary();opened.assert_called_once_with(e['source_xml'])
        Path(e['source_xml']).unlink();p.choose();self.assertFalse(p.buttons['xml'].enabled);self.assertIn('已移动',p.detail_text.get());self.assertFalse(errors)
    def test_history_curve_reopens_without_regeneration_until_source_changes(self):
        app,root,errors=self.app();p,value=self.mount(app,root);calls=[]
        def writer(data,e):
            calls.append(e);file=root/('curve'+str(len(calls))+'.html');file.write_text('fixture');return str(file)
        with patch('control_record_browser.save_curve',side_effect=writer),patch('control_record_browser.os.startfile') as opened:
            p.curve();p.curve();self.pump(app,.25);self.assertEqual(len(calls),1);first=p.exporter.path;p.curve();self.assertEqual(len(calls),1);self.assertEqual(opened.call_count,2);Path(p.selected['file']).write_text('changed');p.curve();self.pump(app,.25);self.assertEqual(len(calls),2);self.assertNotEqual(p.exporter.path,first)
        self.assertEqual(Path(first).read_text(),'fixture');self.assertTrue(p.saved_frame.winfo_ismapped());self.assertFalse(errors)
    def test_curve_browser_failure_retains_saved_path_and_failure_keeps_previous_report(self):
        app,root,errors=self.app();p,value=self.mount(app,root);file=root/'saved.html';file.write_text('keep')
        with patch('control_record_browser.save_curve',return_value=str(file)),patch('control_record_browser.os.startfile',side_effect=OSError('browser fixture')):p.curve();self.pump(app,.25)
        self.assertEqual(p.saved.get(),str(file));self.assertIn('browser fixture',p.status.get());caption=p.exporter.caption;p.table.selection_set((p.table.order[1],))
        with patch('control_record_browser.save_curve',side_effect=OSError('write fixture')):p.curve();self.pump(app,.25)
        self.assertEqual(p.exporter.path,str(file));self.assertEqual(p.exporter.caption,caption);self.assertEqual(file.read_text(),'keep');self.assertTrue(p.buttons['reopen'].enabled);self.assertFalse(errors)
    def test_curve_completion_after_leaving_page_saves_without_opening_browser(self):
        app,root,errors=self.app();p,value=self.mount(app,root);jobs=[];file=root/'later.html';file.write_text('fixture')
        with patch.object(app,'run_background',side_effect=lambda work,done:jobs.append(done)),patch('control_record_browser.os.startfile') as opened:
            p.curve();app.show_page(0);self.pump(app,.05);jobs[0](str(file),None);opened.assert_not_called()
        self.assertEqual(app.history_curve_export.path,str(file));self.assertIn(str(file),app.status.get());self.assertIsNone(app.history_curve_export.page);self.assertFalse(errors)
    def test_both_views_keep_column_preferences_selection_and_status_during_translation(self):
        import i18n
        app,root,errors=self.app()
        try:
            for kind in ('history','official'):
                p,value=self.mount(app,root,kind);p.table.selection_set((p.table.order[4],));identity=p.identity(p.selected);p.table.widths['date']=333;p.table.configure_columns(['date','track'],['date'],{});p.say('打开失败：{error}',error='fixture')
                for language in ('en','zh'):
                    i18n.set_language(language);i18n.refresh(app.root);self.pump(app,.1);self.assertEqual(p.identity(p.selected),identity);self.assertEqual(p.table.widths['date'],333);self.assertEqual(p.table.displaycolumns,['date','track']);self.assertIn('fixture',p.status.get())
        finally:i18n.set_language('zh')
        self.assertFalse(errors)
    def test_double_click_empty_area_does_not_open_previous_record(self):
        app,root,errors=self.app();p,value=self.mount(app,root,'history',histories(root,1))
        with patch.object(p,'primary') as opened:p.double(SimpleNamespace(x=40,y=p.table.viewport.winfo_height()-2));opened.assert_not_called()
        self.assertFalse(errors)
    def test_real_xml_sync_keeps_source_bytes_and_uses_existing_parser_rules(self):
        app,root,errors=self.app();p,value=self.mount(app,root,'official',dict(entries=[],errors=[],conflicts=[]));fixture=official(root,1);source=Path(fixture['source_directory']);xml=source/'race.xml';before=(xml.read_bytes(),xml.stat().st_mtime_ns);p.driver.set('Me');p.sync_folder(source);self.pump(app,.4)
        self.assertFalse(p.loader.running);self.assertEqual(len(p.entries),1);result=next(iter(p.entries.values()));self.assertEqual(result['finish_class_place'],1);self.assertEqual(result['best_lap_s'],99.5);self.assertEqual(result['laps'][0]['sectors'],[30.,31.,39.]);self.assertEqual((xml.read_bytes(),xml.stat().st_mtime_ns),before);self.assertEqual(p.driver_field.entry.cget('state'),'normal');self.assertFalse(errors)
    def test_export_return_to_new_page_shows_saved_result_without_opening_browser(self):
        app,root,errors=self.app();p,value=self.mount(app,root);jobs=[];file=root/'returned.html';file.write_text('fixture')
        with patch.object(app,'run_background',side_effect=lambda work,done:jobs.append(done)),patch('control_record_browser.os.startfile') as opened:
            p.curve();app.show_page(0);self.pump(app,.05);app.personal_record_view='history';app.show_page(6);self.pump(app,.05);current=app.record_loaders['history'].page;self.assertTrue(current.exporter.busy);self.assertFalse(current.buttons['curve'].enabled);jobs[1](value,None);jobs[0](str(file),None);opened.assert_not_called()
        self.assertEqual(current.saved.get(),str(file));self.assertTrue(current.buttons['reopen'].enabled);self.assertFalse(errors)
    def test_f5_and_enter_work_once_and_page_disposal_removes_shortcut_binding(self):
        app,root,errors=self.app();baseline=app.root.bind('<F5>');p,value=self.mount(app,root)
        with patch.object(p,'primary') as opened,patch.object(p.loader,'read') as refreshed:
            p.table.viewport.focus_force();self.pump(app,.05);p.table.viewport.event_generate('<Return>');self.pump(app,.05);p.table.viewport.event_generate('<F5>');self.pump(app,.05);opened.assert_called_once();refreshed.assert_called_once()
        app.show_page(0);self.pump(app,.05);self.assertEqual(app.root.bind('<F5>'),baseline);self.assertFalse(errors)
    def test_switching_sibling_tabs_preserves_outer_scroll_position(self):
        app,root,errors=self.app();p,value=self.mount(app,root);app.scroll.yview_moveto(.35);self.pump(app,.15);position=app.scroll.yview()[0]
        with patch('control_official_results.read_results',return_value=official(root)):self.tab(app,'官方战绩')
        with patch('control_history.read_history',return_value=value):self.tab(app,'纪录履历')
        self.pump(app,.15);self.assertAlmostEqual(app.scroll.yview()[0],position,delta=.025);self.assertFalse(errors)
    def test_real_english_official_mount_and_long_metrics_settle_without_resize_loop(self):
        import i18n
        app,root,errors=self.app();p,value=self.mount(app,root)
        with patch('control_history.read_history',return_value=value):app.toggle_language();self.pump(app,.2)
        self.assertEqual(i18n.language,'en')
        with patch('control_official_results.read_results',return_value=official(root)):self.tab(app,'官方战绩')
        current=app.record_loaders['official'].page;text='Long vehicle and official result details '*20;current.metrics.set(dict(vehicle=text,source=text));self.pump(app,.15);height=current.metrics.winfo_height();self.pump(app,.15);self.assertEqual(current.metrics.winfo_height(),height);self.assertEqual(current.metrics.values['vehicle'].cget('text'),text)
        for tile,caption,value in zip(current.metrics.tiles,current.metrics.captions,current.metrics.values.values()):
            self.assertLessEqual(caption.winfo_reqwidth(),tile.winfo_width()+2);self.assertLessEqual(value.winfo_reqwidth(),tile.winfo_width()+2)
        self.assertFalse(errors)
