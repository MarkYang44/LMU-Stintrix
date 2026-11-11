"""Sidebar game switcher, one-row headers, section tabs that follow scrolling and state-aware run controls."""
import os,unittest
from unittest.mock import patch
from tests import test_ui_polish69 as helpers


def walk(widget):
    for child in widget.winfo_children():yield child;yield from walk(child)


def centre(widget):return widget.winfo_rooty()+widget.winfo_height()/2


@unittest.skipUnless(os.name=='nt','Native Tk')
class UI(unittest.TestCase):
    app=helpers.UI.app;pump=helpers.UI.pump;settle=helpers.UI.settle

    def test_game_switcher_search_and_global_toggles_live_on_the_rail(self):
        app,root,errors=self.app();self.pump(app,.1)
        for _ in range(2):
            shell=app.shell;box=app.simulator_selector
            self.assertIs(box.master,shell.brand);self.assertTrue(box.winfo_ismapped());self.assertEqual(box.itemcget(box.caption,'text'),'LMU')
            self.assertEqual(box.labels['lmu'],'LMU · Le Mans Ultimate')
            texts=[shell.brand.itemcget(i,'text') for i in shell.brand.find_all() if shell.brand.type(i)=='text']
            self.assertNotIn('LE MANS ULTIMATE',texts)
            # App-wide controls live on the rail: search under the switcher,
            # theme and language at its foot; the header is the page's alone.
            for control in (shell.palette_button,shell.theme_button,shell.language_button):
                self.assertTrue(str(control).startswith(str(shell.side)));self.assertTrue(control.winfo_ismapped())
            self.assertLess(box.winfo_rooty(),shell.palette_button.winfo_rooty())
            self.assertLessEqual(shell.palette_button.winfo_rooty()+shell.palette_button.winfo_height(),shell.navigation.winfo_rooty())
            self.assertGreaterEqual(shell.theme_button.winfo_rooty(),shell.navigation.winfo_rooty()+shell.navigation.winfo_height())
            self.assertEqual([w for w in shell.title.master.winfo_children() if w.winfo_manager()],[shell.title])
            app.set_theme('light');app.toggle_language();self.pump(app,.3)
        self.assertFalse(errors)

    def test_settings_section_tabs_follow_reading_position_and_arrow_keys(self):
        app,root,errors=self.app();app.request_page(2);self.settle(app,lambda:'endurance' in getattr(app,'form_panels',{}));self.pump(app,.1)
        spy=app.settings_spy;tabs=[button for button,_ in spy.tabs];bodies=[body for _,body in spy.tabs]
        self.assertTrue(tabs[0].selected);self.assertFalse(any(b.selected for b in tabs[1:]))
        target=bodies[2];app.root.update_idletasks()
        app.scroll.yview_moveto(max(0,target.winfo_rooty()-app.content.winfo_rooty()-10)/max(1,app.content.winfo_height()));self.pump(app,.1)
        self.assertIs(spy.current,target);self.assertEqual([b.selected for b in tabs],[False,False,True,False,False])
        app.scroll.yview_moveto(1);self.pump(app,.1);self.assertIs(spy.current,bodies[-1]);self.assertTrue(tabs[-1].selected)
        app.scroll.yview_moveto(0);self.pump(app,.1);tabs[0].focus_force();self.pump(app,.05);before=app.scroll.yview()[0]
        tabs[0].event_generate('<Right>');self.pump(app,.1)
        self.assertIs(app.root.focus_get(),tabs[1]);self.assertTrue(tabs[1].selected);self.assertGreater(app.scroll.yview()[0],before)
        app.request_page(0);self.settle(app);app.request_page(2);self.settle(app);self.assertEqual(len(app.shell.scroll_listeners),1);self.assertFalse(errors)

    def test_live_controls_join_the_start_row_only_while_a_hud_runs(self):
        app,root,errors=self.app();self.pump(app,.1);live=app.live_actions;demo=app.demo_button
        self.assertTrue(all(b.flow_hidden and not b.winfo_ismapped() for b in live));self.assertTrue(demo.winfo_ismapped())
        self.assertTrue(app.start_button.primary);self.assertFalse(app.stop_button.primary)
        self.assertFalse([w for w in walk(app.content) if w.winfo_class()=='Label' and w.cget('text')=='实时控制在启动记录后可用'])
        with patch.object(app,'active',return_value=True):
            app.update_toolbar();self.pump(app,.05)
            self.assertTrue(all(b.winfo_ismapped() and b.enabled for b in live));self.assertFalse(demo.winfo_ismapped())
            self.assertTrue(app.stop_button.primary);self.assertFalse(app.start_button.primary)
        app.update_toolbar();self.pump(app,.05)
        self.assertTrue(all(not b.winfo_ismapped() and not b.enabled for b in live));self.assertTrue(demo.winfo_ismapped());self.assertTrue(app.start_button.primary);self.assertFalse(errors)

    def test_empty_personal_records_point_to_the_run_page(self):
        app,root,errors=self.app();app.request_page(6)
        loaded=lambda:getattr(app,'record_loaders',{}).get('best') is not None and app.record_loaders['best'].page is not None and app.record_loaders['best'].page.populated
        self.settle(app,loaded);table=app.record_loaders['best'].page.table
        self.assertEqual(table.empty_button.label,'前往运行与 HUD');table.empty_button.invoke();self.settle(app);self.assertEqual(app.page,0);self.assertFalse(errors)

    def test_rail_hover_names_each_page_shortcut(self):
        app,root,errors=self.app();self.pump(app,.1);nav=app.shell.navigation
        with patch.object(nav.tip,'request') as request:
            nav.event_generate('<Motion>',x=20,y=round(nav.step*1.5));self.pump(app,.02)
        request.assert_called_once();self.assertEqual(request.call_args.args[0],1);self.assertIn('Ctrl+2',request.call_args.args[1])
        with patch.object(nav.tip,'hide') as hide:nav.event_generate('<Leave>');hide.assert_called()
        self.assertFalse(errors)
