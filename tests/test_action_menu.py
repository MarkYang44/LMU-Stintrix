"""Real Tk workflow tests for contextual actions, dismissal and keyboard access."""
import os,unittest
from types import SimpleNamespace
from unittest.mock import patch
import tests.test_ui_efficiency as efficiency


@unittest.skipUnless(os.name=='nt','Native Windows Tk')
class ActionMenuTests(unittest.TestCase):
    app=efficiency.EfficiencyTests.app
    pump=efficiency.EfficiencyTests.pump
    def ready(self):
        app,root,errors=self.app(True);app.show_page(1);self.pump(app,.6)
        return app,errors
    def test_direct_reports_require_one_session_and_call_original_report(self):
        app,errors=self.ready();self.assertFalse(app.review_actions['laps'].enabled);self.assertFalse(app.review_actions['journal'].enabled)
        with patch.object(app,'report') as report:
            app.review_actions['laps'].invoke();report.assert_not_called()
            app.tree.selection_set((app.tree.get_children()[0],));app.update_selection_count()
            app.review_actions['laps'].invoke();report.assert_called_once_with('圈速单.png');report.reset_mock()
            app.review_actions['journal'].invoke();report.assert_called_once_with('比赛日志.png')
            app.tree.selection_set(app.tree.get_children()[:2]);app.update_selection_count();self.assertFalse(app.review_actions['journal'].enabled)
        self.assertFalse(errors)
    def test_disabled_menu_actions_do_not_run_and_enabled_actions_recheck_selection(self):
        app,errors=self.ready();menu=app.review_menu
        with patch.object(app,'report') as report:
            menu.invoke('fastest');report.assert_not_called()
            app.tree.selection_set((app.tree.get_children()[0],));menu.open();self.pump(app,.2)
            app.tree.selection_set(());menu.invoke('fastest');report.assert_not_called()
            menu.close()
        menu.invoke('all');self.assertEqual(len(app.tree.selection()),len(app.tree.get_children()))
        menu.invoke('clear');self.assertFalse(app.tree.selection());self.assertFalse(errors)
    def test_keyboard_skips_disabled_items_closes_and_releases_bindings(self):
        app,errors=self.ready();menu=app.review_menu
        bindings=lambda:{seq:app.root.bind(seq).strip() for seq in ('<Configure>','<ButtonPress-1>','<FocusOut>')}
        before=bindings()
        with patch.dict(os.environ,{'LMU_STINTRIX_REDUCED_MOTION':'1'}):
            menu.open();self.pump(app,.1);self.assertFalse(menu.motion.jobs)
            self.assertEqual(menu.active,'split')
            menu.key(SimpleNamespace(keysym='End',state=0));self.assertEqual(menu.active,'all')
            menu.key(SimpleNamespace(keysym='Return',state=0));self.assertIsNone(menu.popup);self.assertTrue(app.tree.selection())
        self.assertEqual(before,bindings());self.assertIsNone(app.root._stintrix_active_select)
        self.assertFalse(errors)
    def test_outside_click_passes_through_and_resize_and_navigation_dismiss(self):
        app,errors=self.ready();menu=app.review_menu;menu.open();self.pump(app,.15)
        target=app.review_actions['compare'];fired=[]
        target.bind('<ButtonPress-1>',lambda _:fired.append(True),add='+')
        target.event_generate('<ButtonPress-1>',x=10,y=10);self.pump(app,.1)
        self.assertTrue(fired);self.assertIsNone(menu.popup)
        menu.open();app.root.geometry('1100x720');self.pump(app,.1);self.assertIsNone(menu.popup)
        menu.open();app.show_page(0);self.pump(app,.2);self.assertIsNone(menu.popup);self.assertFalse(menu.bindings);self.assertFalse(errors)
    def test_context_menu_preserves_multi_selection_or_selects_clicked_row(self):
        app,errors=self.ready();tree=app.tree
        ids=tree.get_children();tree.selection_set(ids[:2]);tree.viewport.event_generate('<Button-3>',x=70,y=10)
        self.pump(app,.1);self.assertEqual(tree.selection(),ids[:2]);app.review_menu.close()
        tree.viewport.event_generate('<Button-3>',x=70,y=round(tree.rowheight*2+10));self.pump(app,.1)
        self.assertEqual(tree.selection(),(ids[2],));self.assertTrue(app.review_actions['laps'].enabled);self.assertFalse(errors)
    def test_search_clear_restores_list_and_toolbar_fits_small_window(self):
        app,errors=self.ready();total=len(app.tree.get_children());app.search.set('Fuji');app.populate()
        self.assertLess(len(app.tree.get_children()),total);app.focus_search();app.search_target.clear()
        self.assertEqual(app.search.get(),'');self.assertEqual(len(app.tree.get_children()),total)
        for button in app.review_actions.values():
            self.assertTrue(button.winfo_ismapped());self.assertLessEqual(button.winfo_x()+button.winfo_width(),app.shell.action_host.winfo_width())
        self.assertFalse(errors)
    def test_select_and_action_menu_close_each_other_without_grabbing_input(self):
        app,errors=self.ready();menu=app.review_menu
        select=app.review_filters.choices['track'];menu.open();select.open();self.assertIsNone(menu.popup)
        menu.open();self.assertIsNone(select.popup);self.assertIsNone(app.root.grab_current());menu.close();self.assertFalse(errors)
    def test_popup_stays_inside_short_window_in_both_languages(self):
        app,errors=self.ready();app.root.geometry('1060x700');self.pump(app,.1)
        for _ in range(2):
            menu=app.review_menu;menu.open();self.pump(app,.2);p=menu.popup
            self.assertGreaterEqual(p.winfo_x(),0);self.assertGreaterEqual(p.winfo_y(),0)
            self.assertLessEqual(p.winfo_x()+p.winfo_width(),app.root.winfo_width())
            self.assertLessEqual(p.winfo_y()+p.winfo_height(),app.root.winfo_height())
            self.assertGreater(menu.canvas.winfo_height(),0)
            menu.key(SimpleNamespace(keysym='End',state=0));self.pump(app,.1);top,bottom=menu.positions[menu.active]
            self.assertLessEqual(menu.canvas.canvasy(0),top);self.assertGreaterEqual(menu.canvas.canvasy(0)+menu.canvas.winfo_height()+1,bottom)
            menu.close();app.toggle_language();self.pump(app,.2)
        self.assertFalse(errors)
    def test_theme_switch_reloads_matching_logo_without_losing_selection(self):
        from PIL import Image
        import branding
        app,errors=self.ready();chosen=(app.tree.get_children()[0],);app.tree.selection_set(chosen)
        for mode in ('light','dark','light','dark'):
            app.set_theme(mode);self.pump(app,.1)
            with Image.open(branding.directory()/('menu-icon-light.png' if mode=='light' else 'menu-icon.png')) as image:
                self.assertEqual(app.shell.logo_source.tobytes(),image.convert('RGBA').tobytes())
            self.assertEqual(app.tree.selection(),chosen)
        self.assertFalse(errors)
