"""Grouped rail with settings at its foot, page-only headers, one home for app preferences, fixed view tabs."""
import os,unittest
from unittest.mock import patch
from tests import test_ui_polish69 as helpers


def walk(widget):
    for child in widget.winfo_children():yield child;yield from walk(child)


def centre(widget):return widget.winfo_rooty()+widget.winfo_height()/2


class Source(unittest.TestCase):
    def test_rail_order_groups_and_names(self):
        import control_center,control_shell,platform_runtime
        with patch.object(platform_runtime,'offline_only',return_value=False):self.assertEqual(platform_runtime.page_ids(),(0,1,6,4,5,3,2))
        with patch.object(platform_runtime,'offline_only',return_value=True):self.assertEqual(platform_runtime.page_ids(),(1,6,4,5,3,2))
        self.assertEqual(control_center.PAGES[2],'设置')
        # Every page belongs to a captioned group except settings, pinned at the foot.
        self.assertEqual({page for page,group in control_shell.GROUPS.items() if not group},{2})
        self.assertEqual(set(control_shell.GROUPS),set(range(7)))

    def test_page_disposal_never_retires_shared_shell_variables(self):
        import tkinter as tk
        from control_disposal import release
        from control_pages import Page
        root=tk.Tk();root.withdraw()
        try:
            shared=tk.StringVar(root,value='dark');shared.shared=True;own=tk.StringVar(root,value='x')
            frame=tk.Frame(root);holder=tk.Frame(frame);holder.mirror=shared;holder.value=own
            release(Page(frame),type('Owner',(),{})())
            self.assertIsNotNone(shared._tk);self.assertEqual(shared.get(),'dark');self.assertIsNone(own._tk)
        finally:root.destroy()


@unittest.skipUnless(os.name=='nt','Native Tk')
class UI(unittest.TestCase):
    app=helpers.UI.app;pump=helpers.UI.pump;settle=helpers.UI.settle

    def test_rail_captions_groups_and_pinned_settings_follow_window_height(self):
        app,root,errors=self.app();app.root.geometry('1200x1000');self.pump(app,.2);nav=app.shell.navigation
        texts=[nav.itemcget(i,'text') for i in nav.find_all() if nav.type(i)=='text']
        for caption in ('实时','分析','资料','工具'):self.assertIn(caption,texts)
        settings=nav.ids.index(2);top,height=nav.boxes[settings]
        # Settings rests at the rail's foot, below every other entry.
        self.assertAlmostEqual(top+height,nav.winfo_height(),delta=2)
        self.assertTrue(all(nav.boxes[i][0]+nav.boxes[i][1]<=top for i in range(len(nav.names)) if i!=settings))
        # Clicking a row opens that row's page, wherever groups put it.
        records=nav.ids.index(6);row_top,row_height=nav.boxes[records]
        nav.event_generate('<Button-1>',x=nav.winfo_width()//2,y=round(row_top+row_height/2));self.settle(app,lambda:app.page==6)
        self.assertEqual(nav.selected,records)
        # A short window drops the captions before rows get cramped.
        app.root.minsize(1,1);app.root.geometry('1200x600');self.pump(app,.2)
        texts=[nav.itemcget(i,'text') for i in nav.find_all() if nav.type(i)=='text']
        self.assertNotIn('分析',texts);self.assertGreaterEqual(nav.step,nav.MINIMUM*nav.s-1)
        self.assertAlmostEqual(sum(nav.boxes[settings]),nav.winfo_height(),delta=2);self.assertFalse(errors)

    def test_settings_mirror_theme_and_language_without_losing_the_rail_toggles(self):
        app,root,errors=self.app();app.request_page(2);self.settle(app,lambda:'theme' in getattr(app,'app_preference_controls',{}))
        controls=app.app_preference_controls
        self.assertIs(controls['theme'].variable,app.shell.theme_var);self.assertIs(controls['language'].variable,app.shell.language_var)
        controls['theme'].select(1);self.pump(app,.1)
        self.assertEqual(app.shell.theme_var.get(),'light');self.assertEqual(app.shell.theme_button.index(),1)
        app.app_preference_controls['language'].select(1);self.pump(app,.3)
        import i18n
        self.assertEqual(i18n.language,'en');self.assertEqual(app.page,2)
        self.assertIsNotNone(app.shell.language_var._tk);self.assertEqual(app.shell.language_button.index(),1)
        app.toggle_language();self.pump(app,.3);self.assertEqual(i18n.language,'zh');self.assertFalse(errors)

    def test_record_and_data_tabs_stay_fixed_above_page_actions(self):
        app,root,errors=self.app(True);app.request_page(6);self.settle(app);self.pump(app,.2)
        tabs=app.personal_record_tabs;host=app.shell.tab_host
        self.assertTrue(all(str(tab).startswith(str(host)) for tab in tabs.values()))
        self.assertLess(host.winfo_rooty(),app.shell.action_host.winfo_rooty())
        y=tabs['best'].winfo_rooty();tabs['podium'].invoke();self.settle(app);self.pump(app,.1)
        self.assertEqual(tabs['podium'].winfo_rooty(),y);self.assertTrue(tabs['podium'].selected)
        app.scroll.yview_moveto(1);self.pump(app,.1);self.assertEqual(tabs['podium'].winfo_rooty(),y)
        app.request_page(3);self.settle(app);self.pump(app,.1)
        self.assertTrue(all(not tab.winfo_exists() for tab in tabs.values()))
        self.assertTrue(all(str(tab).startswith(str(host)) for tab in app.data_tasks.buttons.values()))
        app.request_page(1);self.settle(app);self.assertFalse(host.winfo_children());self.assertFalse(host.winfo_manager());self.assertFalse(errors)

    def test_review_toolbar_is_compact_and_ends_with_menu_and_delete(self):
        app,root,errors=self.app(True);app.root.geometry('1400x820');app.request_page(1);self.settle(app);self.pump(app,.2)
        host=app.shell.action_host;actions=app.review_actions
        delete=actions['delete']
        self.assertAlmostEqual(delete.winfo_x()+delete.winfo_width(),host.winfo_width(),delta=2)
        self.assertEqual(actions['open'].winfo_rooty(),delete.winfo_rooty())
        for button in actions.values():self.assertLessEqual(button.winfo_height(),round(38*button.s)+1)
        # The page's search names what it matches; no separate caption.
        self.assertEqual(app.search_target.placeholder,'搜索时间、赛道、车辆或阶段')
        self.assertFalse([w for w in walk(app.content) if w.winfo_class()=='Label' and w.cget('text')=='搜索'])
        app.root.geometry('1060x700');self.pump(app,.2)
        for button in actions.values():self.assertLessEqual(button.winfo_x()+button.winfo_width(),host.winfo_width()+1)
        self.assertFalse(errors)

    def test_run_commands_share_the_status_line_and_card_tools_their_title(self):
        app,root,errors=self.app();self.pump(app,.1)
        self.assertEqual([b for b in app.run_commands.pack_slaves()],[app.demo_button,app.start_button])
        with patch.object(app,'active',return_value=True):
            app.update_toolbar();self.pump(app,.05);self.assertEqual(app.run_commands.pack_slaves(),[app.stop_button])
        app.update_toolbar();self.pump(app,.05);self.assertEqual(app.run_commands.pack_slaves(),[app.demo_button,app.start_button])
        labels={getattr(w,'label',None) for w in walk(app.content)}
        self.assertIn('HUD 布局',labels);self.assertNotIn('全局快捷键',labels);self.assertFalse(errors)


if __name__=='__main__':unittest.main()
