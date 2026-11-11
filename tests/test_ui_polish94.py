"""One browsing pattern for every list: rail footer, page tray, record views, settings intro."""
import os,unittest
from unittest.mock import patch
from tests import test_ui_polish69 as helpers


def walk(widget):
    for child in widget.winfo_children():yield child;yield from walk(child)


class Source(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        self.root=tk.Tk();self.root.withdraw();self.addCleanup(self.root.destroy)

    def test_drawn_icons_and_icon_segments_need_no_icon_font(self):
        import tkinter as tk
        from control_widgets import glyph,Segmented
        canvas=tk.Canvas(self.root,width=60,height=40)
        glyph(canvas,'moon',20,20,1,'#ffffff');glyph(canvas,'sun',40,20,1,'#ffffff')
        kinds=[canvas.type(item) for item in canvas.find_all()]
        self.assertEqual(kinds.count('polygon'),1);self.assertEqual(kinds.count('oval'),1);self.assertEqual(kinds.count('line'),8)
        self.assertGreaterEqual(len(canvas.coords(canvas.find_withtag('all')[0])),12)
        variable=tk.StringVar(self.root,value='dark')
        control=Segmented(self.root,variable,['dark','light'],None,{'dark':'深色','light':'浅色'},{'dark':'深色主题','light':'浅色主题'},{'dark':'moon','light':'sun'})
        control.configure(width=72,height=34);control.pack();self.root.update()
        texts=[control.itemcget(item,'text') for item in control.find_all() if control.type(item)=='text']
        # Icon segments draw no caption text; their titles still name them on hover.
        self.assertEqual(texts,[]);self.assertEqual(control.titles['light'],'浅色主题')
        control.select(1);self.assertEqual(variable.get(),'light')

    def test_link_answers_label_queries_and_respects_state(self):
        from control_widgets import Link
        calls=[];link=Link(self.root,'重置筛选',lambda:calls.append(1))
        # Theme recolouring reads every option; a link must answer like a Label.
        self.assertIn('foreground',link.configure());self.assertEqual(link.cget('state'),'normal')
        link.invoke();link.configure(state='disabled');link.invoke();self.assertEqual(calls,[1]);self.assertFalse(link.enabled)
        link.configure(state='normal',text='资料说明 ▾');self.assertEqual(link.label,'资料说明 ▾');self.assertEqual(link.cget('text'),'资料说明 ▾')

    def test_collapsed_status_mark_takes_room_only_with_news(self):
        import tkinter as tk,time
        from control_feedback import StatusFeedback
        status=tk.StringVar(self.root,value='2 条个人赛道纪录');line=StatusFeedback(self.root,status,collapse=True);line.pack(fill='x');self.root.update()
        self.assertFalse(line.icon.winfo_manager())
        line.busy('load');self.root.update();self.assertFalse(line.icon.winfo_manager())
        end=time.monotonic()+.4
        while time.monotonic()<end:self.root.update();time.sleep(.01)
        self.assertTrue(line.icon.winfo_manager())
        line.busy('load',False);self.root.update();self.assertFalse(line.icon.winfo_manager())
        # A quick job that ends before the delay never moves the text.
        line.busy('quick');line.busy('quick',False)
        end=time.monotonic()+.3
        while time.monotonic()<end:self.root.update();time.sleep(.01)
        self.assertFalse(line.icon.winfo_manager())
        status.set('设置已保存');self.root.update();self.assertTrue(line.icon.winfo_manager())


@unittest.skipUnless(os.name=='nt','Native Tk')
class UI(unittest.TestCase):
    app=helpers.UI.app;pump=helpers.UI.pump;settle=helpers.UI.settle

    def test_rail_toggles_share_one_row_and_groups_keep_captions(self):
        app,root,errors=self.app();shell=app.shell
        for geometry in ('1240x850','1060x760'):
            app.root.geometry(geometry);self.pump(app,.2)
            self.assertEqual(shell.theme_button.winfo_rooty(),shell.language_button.winfo_rooty())
            self.assertLess(shell.theme_button.winfo_width(),shell.language_button.winfo_width())
            texts=[shell.navigation.itemcget(i,'text') for i in shell.navigation.find_all() if shell.navigation.type(i)=='text']
            self.assertIn('分析',texts,geometry)
        self.assertEqual(shell.theme_button.icons,{'dark':'moon','light':'sun'})
        shell.theme_button.select(1);self.pump(app,.2);self.assertEqual(app.shell.theme_var.get(),'light');self.assertFalse(errors)

    def test_page_that_fits_shows_no_scrollbar_thumb(self):
        app,root,errors=self.app();app.root.geometry('1240x900');app.request_page(3);self.settle(app);self.pump(app,.2)
        self.assertEqual(str(app.shell.bar.cget('style')),'Lab.Idle.Vertical.TScrollbar')
        app.request_page(2);self.settle(app);self.pump(app,.2)
        self.assertEqual(str(app.shell.bar.cget('style')),'Lab.Vertical.TScrollbar');self.assertFalse(errors)

    def test_guide_header_fits_one_line_and_comparison_rests_in_the_tray(self):
        app,root,errors=self.app();app.request_page(5);self.settle(app);g=app.guide_page;shell=app.shell;self.pump(app,.1)
        # The flow layout centres each control on its line: one line is as tall as its tallest control.
        placed=[child for child in shell.action_host.winfo_children() if child.winfo_manager()]
        self.assertLessEqual(shell.action_host.winfo_height(),max(child.winfo_height() for child in placed)+1,'the guide toolbar wraps at the minimum window width')
        self.assertEqual(len({child.winfo_y()+child.winfo_height()//2 for child in placed}),1)
        self.assertFalse(shell.tray_host.winfo_manager());self.assertFalse(g.reset_button.winfo_manager())
        self.assertTrue(str(g.fixed_actions['compare']).startswith(str(shell.tray_host)))
        for key in list(g.library.data['cars'])[:2]:g.select('car:'+key)
        self.pump(app,.1);self.assertTrue(shell.tray_host.winfo_ismapped());self.assertTrue(g.compare_button.enabled)
        top=g.compare_button.winfo_rooty();app.scroll.yview_moveto(.6);self.pump(app,.1);self.assertEqual(g.compare_button.winfo_rooty(),top)
        g.compare_button.invoke();self.settle(app);self.assertEqual(g.state['mode'],'compare');self.assertEqual(g.compare_button.label,'返回资料列表')
        g.compare_button.invoke();self.settle(app);self.assertEqual(g.state['mode'],'browse')
        g.variables['group'].set('LMGT3');g.filter_changed();self.settle(app);self.assertTrue(g.reset_button.winfo_ismapped());self.assertTrue(g.reset_button.enabled)
        g.reset_button.invoke();self.settle(app);self.assertFalse(g.reset_button.winfo_manager())
        g.clear();self.settle(app);self.assertFalse(shell.tray_host.winfo_manager())
        g.select('car:'+next(iter(g.library.data['cars'])));app.request_page(1);self.settle(app)
        self.assertFalse(shell.tray_host.winfo_children());self.assertFalse(shell.tray_host.winfo_manager());self.assertFalse(errors)

    def test_record_views_share_search_tools_status_and_rows(self):
        app,root,errors=self.app(True);app.root.geometry('1240x850');app.request_page(6);self.settle(app);self.pump(app,.3)
        for kind in ('best','podium','history','official'):
            if kind!='best':app.personal_record_tabs[kind].invoke();self.settle(app);self.pump(app,.3)
            page=app.record_loaders[kind].page;row=page.search_field.master
            tools=[page.search_field,page.buttons['filters'],page.buttons['refresh']]
            self.assertTrue(all(widget.master is row for widget in tools),kind)
            self.assertEqual(sorted(tools,key=lambda w:w.winfo_x()),tools,kind)
            self.assertFalse(page.buttons['refresh'].primary,kind)
            siblings=row.master.pack_slaves();self.assertIs(siblings[siblings.index(row)+1],page.feedback,kind)
            self.assertAlmostEqual(page.feedback.label.winfo_rootx(),page.search_field.winfo_rootx(),delta=2)
            if kind=='podium':
                # Placings are a tab strip, not primary-filled actions.
                from control_video_widgets import Tab
                self.assertTrue(all(isinstance(button,Tab) for button in page.category_buttons.values()))
                page.choose_category(2);self.assertEqual([b.selected for b in page.category_buttons.values()],[False,False,True,False])
                self.assertFalse(any(b.primary for b in page.category_buttons.values()))
        self.assertFalse(errors)

    def test_settings_open_with_a_titled_recording_section(self):
        app,root,errors=self.app();app.root.geometry('1240x850');app.request_page(2);self.settle(app);self.pump(app,.2)
        title,body=app.settings_anchors[0];self.assertEqual(title,'接口')
        self.assertEqual(body.heading.cget('text'),'记录与数据接口')
        switch=next(w for w in walk(body) if getattr(w,'variable',None) is app.practice_recording)
        # The switch spans the section like every setting row: control at the right edge.
        self.assertGreater(switch.winfo_width(),body.winfo_width()*.9)
        check=next(w for w in walk(body) if getattr(w,'label',None)=='检查数据接口')
        self.assertIs(check.master,app.sampling_summary.master);self.assertIn('120',app.sampling_summary.cget('text'))
        self.assertAlmostEqual(check.winfo_rootx()+check.winfo_width(),body.winfo_rootx()+body.winfo_width(),delta=3);self.assertFalse(errors)


if __name__=='__main__':unittest.main()
