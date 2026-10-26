"""Cell inspection, context selection and DPI retain original browsing behavior."""
import json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from tests import test_ui_efficiency as helpers


@unittest.skipUnless(os.name=='nt','Native Windows Tk')
class UI(unittest.TestCase):
    app=helpers.EfficiencyTests.app;pump=helpers.EfficiencyTests.pump
    def best(self):
        app,root,errors=self.app(True);app.show_page(6);self.pump(app,.45);return app,root,errors,app.record_loaders['best'].page
    def library(self):
        from control_library import show
        app,root,errors=self.app(True);window=show(app,root,Mock(),Mock());self.pump(app,.4);self.assertFalse(window.library.loading);return app,root,errors,window.library
    def test_keyboard_columns_follow_frozen_order_reveal_column_and_keep_selection(self):
        from control_cell_details import move,current,columns
        app,root,errors,p=self.best();t=p.table;selected=t.selection();t.viewport.focus_force();self.pump(app,.03)
        for _ in range(len(t.columns)+2):move(t,1)
        self.assertEqual(current(t)[1],columns(t)[-1]);self.assertGreater(t.xoffset,0);self.assertEqual(t.selection(),selected);self.assertFalse(t.motion.jobs)
        for _ in range(len(t.columns)+2):move(t,-1)
        self.assertEqual(current(t)[1],'track');self.assertEqual(t.selection(),selected);self.assertFalse(errors)
    def test_inspector_keeps_every_character_and_copy_uses_the_bound_snapshot(self):
        from control_cell_details import show
        app,root,errors,p=self.best();t=p.table;iid=t.selection()[0];t.focus_column='layout';index=t.columns.index('layout');value=('完整文字\t"quoted"\n'*240)+'末尾';row=list(t.rows[iid]);row[index]=value;t.rows[iid]=tuple(row)
        files={f:f.read_bytes() for f in (root/'Logs').glob('*/session.json')};selection=t.selection();window=show(t);snapshot=window.cell_snapshot
        self.assertEqual(snapshot['text'].get('1.0','end-1c'),value);self.assertEqual(snapshot['text'].cget('state'),'disabled')
        row[index]='changed after opening';t.rows[iid]=tuple(row)
        with patch.object(window,'clipboard_clear'),patch.object(window,'clipboard_append') as append:snapshot['copy']();append.assert_called_once_with(value)
        replacement=show(t);self.assertIsNot(replacement,window);self.assertEqual(replacement.cell_snapshot['value'],'changed after opening');self.assertEqual(t.selection(),selection)
        for f,raw in files.items():self.assertEqual(f.read_bytes(),raw)
        replacement.destroy();self.assertFalse(errors)
    def test_empty_selection_does_not_create_inspector_or_change_view(self):
        from control_cell_details import show,move
        app,root,errors,p=self.best();t=p.table;t.selection_set(());before=t.xoffset;self.assertIsNone(show(t));move(t,1);self.assertEqual(t.xoffset,before);self.assertFalse(errors)
    def test_f2_and_escape_restore_list_focus_and_leaving_page_closes_inspector(self):
        app,root,errors,p=self.best();t=p.table;app.root.focus_force();t.viewport.focus_set();t.viewport.event_generate('<F2>');self.pump(app,.08);window=t.cell_details;self.assertTrue(window.winfo_exists());window.event_generate('<Escape>');self.pump(app,.05);self.assertIsNone(t.cell_details);self.assertIs(app.root.focus_get(),t.viewport)
        t.viewport.event_generate('<F2>');self.pump(app,.05);window=t.cell_details;app.show_page(0);self.pump(app,.15);self.assertFalse(window.winfo_exists());self.assertFalse(errors)
    def test_library_right_click_keeps_multi_selection_and_copies_the_clicked_cell(self):
        app,root,errors,v=self.library();t=v.table;ids=t.get_children();t.selection_set(ids[:2]);v.window.focus_force();self.pump(app,.03)
        x=t.widths['date']+20;t.viewport.event_generate('<Button-3>',x=round(x),y=round(t.rowheight+10));self.pump(app,.16)
        self.assertEqual(t.selection(),ids[:2]);self.assertEqual(t.cursor,ids[1]);self.assertEqual(t.focus_column,'track')
        with patch.object(t,'copy_text') as copied:v.operations.menu.invoke('copy-cell');copied.assert_called_once_with(t.rows[ids[1]][t.columns.index('track')])
        self.assertIs(v.window.focus_get(),t.viewport);self.assertEqual(t.selection(),ids[:2]);v.close();self.assertFalse(errors)
    def test_library_unselected_context_selects_one_and_blank_area_keeps_it(self):
        app,root,errors,v=self.library();t=v.table;ids=t.get_children();t.selection_set(ids[:2]);t.viewport.event_generate('<Button-3>',x=50,y=round(t.rowheight*2+10));self.pump(app,.16);self.assertEqual(t.selection(),(ids[2],))
        t.viewport.event_generate('<Button-3>',x=50,y=round(t.rowheight*20));self.pump(app,.03);self.assertIsNone(v.operations.menu.popup);self.assertEqual(t.selection(),(ids[2],));v.close();self.assertFalse(errors)
    def test_keyboard_context_is_bounded_and_disposed_without_owner_bindings(self):
        app,root,errors,v=self.library();v.window.geometry('900x650');app.toggle_language();self.pump(app,.2);t=v.table;t.selection_set(t.get_children()[:2]);v.window.focus_force();t.viewport.focus_set()
        sequences=('<Configure>','<ButtonPress-1>','<FocusOut>');before={s:v.window.bind(s) for s in sequences};t.viewport.event_generate('<Shift-F10>');self.pump(app,.16);menu=v.operations.menu;self.assertTrue(menu.popup)
        panel=menu.popup;self.assertGreaterEqual(panel.winfo_y(),0);self.assertLessEqual(panel.winfo_y()+panel.winfo_height(),v.window.winfo_height());menu.close();self.assertEqual({s:v.window.bind(s) for s in sequences},before);menu.open();v.close();self.assertIsNone(menu.popup);self.assertFalse(menu.bindings);self.assertFalse(errors)
    def test_open_directory_uses_bound_local_folder_and_refuses_missing_or_outside(self):
        app,root,errors,v=self.library();t=v.table;key=t.get_children()[0];t.selection_set((key,));folder=Path(v.items[key]['folder'])
        with patch('control_library_actions.os.startfile') as opened:v.operations.menu.invoke('folder');opened.assert_called_once_with(str(folder.resolve()))
        v.items[key]['folder']=str(root.parent/'outside')
        with patch('control_library_actions.os.startfile') as opened:v.operations.open_directory();opened.assert_not_called()
        self.assertTrue(v.status.get());v.close();self.assertFalse(errors)
    def test_library_search_hint_is_not_query_and_f2_window_fits_english_minimum(self):
        from control_cell_details import show
        from control_video_widgets import Action
        app,root,errors,v=self.library();self.assertEqual(v.query.get(),'');self.assertTrue(v.search.placeholder_label.winfo_ismapped());app.set_theme('light');app.toggle_language();self.pump(app,.2);self.assertEqual(v.search.placeholder_label.cget('text'),'Search circuit, car, date or notes')
        v.table.selection_set(v.table.get_children()[:1]);window=show(v.table);window.geometry('460x320');self.pump(app,.15)
        def walk(w):
            yield w
            for c in w.winfo_children():yield from walk(c)
        for button in (w for w in walk(window) if isinstance(w,Action)):
            self.assertLessEqual(button.winfo_rootx()+button.winfo_width(),window.winfo_rootx()+window.winfo_width());self.assertLessEqual(button.winfo_rooty()+button.winfo_height(),window.winfo_rooty()+window.winfo_height())
        window.destroy();v.close();self.assertFalse(errors)
    def test_related_default_columns_scale_at_125_percent_and_do_not_rewrite_preferences(self):
        import tkinter as tk
        from control_center import ControlCenter
        from control_library import show
        from tools.capture_readme import sessions
        with tempfile.TemporaryDirectory(dir=helpers.ROOT/'_local') as tmp,patch('control_center.ROOT',Path(tmp)),patch('control_center.ControlCenter.repair_windows_entry'):
            root=Path(tmp);sessions(root);window=tk.Tk();window.tk.call('tk','scaling',120/72);app=ControlCenter(window);errors=[];window.report_callback_exception=lambda *e:errors.append(e)
            try:
                for kind in ('history','podium','official'):
                    app.personal_record_view=kind;app.show_page(6);self.pump(app,.35);t=app.record_loaders[kind].page.table
                    if 'class' in t.columns:self.assertGreaterEqual(t.actual['class'],t.font.measure('LMGT3')+24*t.s)
                    self.assertGreaterEqual(t.widths['date'],170*t.s)
                w=show(app,root,Mock(),Mock());self.pump(app,.35);self.assertGreaterEqual(w.library.table.widths['date'],165*w.library.table.s);w.destroy();self.assertFalse((root/'table_views.json').exists());self.assertFalse(errors)
            finally:
                app.close()
                while app.pages.owner is not None:app.root.update()
    def test_sibling_filters_start_collapsed_and_leave_real_rows_visible(self):
        app,root,errors=self.app(True);app.root.geometry('1240x850')
        for kind in ('podium','history','official'):
            app.personal_record_view=kind;app.show_page(6);self.pump(app,.35);p=app.record_loaders[kind].page;self.assertFalse(p.modes.winfo_manager());self.assertTrue(p.buttons['filters'].winfo_ismapped())
            remaining=app.scroll.winfo_rooty()+app.scroll.winfo_height()-p.table.viewport.winfo_rooty();self.assertGreaterEqual(remaining,2*p.table.rowheight,kind)
        self.assertFalse(errors)
    def test_filter_expansion_active_count_and_query_survive_leaving_and_translation(self):
        app,root,errors=self.app(True);app.personal_record_view='history';app.show_page(6);self.pump(app,.4);p=app.record_loaders['history'].page;p.buttons['filters'].invoke();self.assertTrue(p.modes.winfo_manager());p.modes.state['mode']='single';p.query.set('Fuji');p.populate_history();self.assertIn('1',p.buttons['filters'].cget('text'));selected=p.table.selection()
        app.show_page(0);app.personal_record_view='history';app.show_page(6);self.pump(app,.4);p=app.record_loaders['history'].page;self.assertTrue(p.modes.winfo_manager());self.assertEqual(p.query.get(),'Fuji');self.assertEqual(p.modes.state['mode'],'single');self.assertEqual(p.table.selection(),selected)
        p.buttons['filters'].invoke();app.toggle_language();self.pump(app,.25);p=app.record_loaders['history'].page;self.assertFalse(p.modes.winfo_manager());self.assertIn('Filters',p.buttons['filters'].cget('text'));self.assertIn('1',p.buttons['filters'].cget('text'));self.assertEqual(p.query.get(),'Fuji');self.assertFalse(errors)
