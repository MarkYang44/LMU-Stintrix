"""Records list and details on one screen, and the F1 keyboard sheet."""
import os,time,unittest
from tests import test_ui_polish69 as helpers


def walk(widget):
    for child in widget.winfo_children():yield child;yield from walk(child)


def wait(root,condition,seconds=3):
    deadline=time.monotonic()+seconds
    while not condition() and time.monotonic()<deadline:root.update();time.sleep(.005)
    return condition()


@unittest.skipUnless(os.name=='nt','Native Tk')
class UI(unittest.TestCase):
    app=helpers.UI.app;pump=helpers.UI.pump;settle=helpers.UI.settle

    def best(self,app):
        app.request_page(6);loaded=lambda:getattr(app,'record_loaders',{}).get('best') is not None and app.record_loaders['best'].page is not None and app.record_loaders['best'].page.fixed
        self.settle(app,loaded);self.pump(app,.2);return app.record_loaders['best'].page

    def test_short_record_lists_hug_their_rows_so_details_share_the_screen(self):
        app,root,errors=self.app(True);app.root.geometry('1400x900');p=self.best(app);t=p.table
        self.assertEqual(len(t.order),2);self.assertTrue(wait(app.root,lambda:int(t.viewport.cget('height'))==round(3*t.rowheight)))
        self.pump(app,.1);info=p.view_layout.info;bottom=app.scroll.winfo_rooty()+app.scroll.winfo_height()
        self.assertLess(info.winfo_rooty()+60,bottom)
        p.query.set('no such record');p.search_field.flush();self.pump(app,.2)
        self.assertEqual(len(t.order),0);self.assertTrue(wait(app.root,lambda:int(t.viewport.cget('height'))>=round(4*t.rowheight)));self.assertFalse(errors)

    def test_f1_lists_shortcuts_and_closes_like_the_palette(self):
        app,root,errors=self.app();self.settle(app);sheet=app.shortcut_sheet;button=app.shell.theme_button
        app.root.focus_force();button.focus_set();self.pump(app,.05)
        app.root.event_generate('<F1>');self.assertTrue(sheet.opened);self.assertIs(sheet.frame.master,app.root);self.pump(app,.05);self.assertIs(app.root.focus_get(),sheet.frame)
        texts=[w.cget('text') for w in walk(sheet.frame) if w.winfo_class()=='Label']
        self.assertIn('快速跳转：页面、操作、设置、赛道与车型',texts);self.assertIn('Ctrl',texts);self.assertIn('F5',texts)
        sheet.frame.event_generate('<Escape>');self.pump(app,.02);self.assertFalse(sheet.opened);self.assertIs(app.root.focus_get(),button)
        sheet.open();app.palette.open();self.assertFalse(sheet.opened);self.assertTrue(app.palette.opened)
        app.palette.query.set('键盘');self.assertEqual((app.palette.rows[0][2].key,app.palette.rows[0][2].shortcut),('keys','F1'))
        app.palette.choose(keyboard=True);self.assertTrue(sheet.opened);self.assertFalse(app.palette.opened)
        app.shell.title.event_generate('<Button-1>',x=2,y=2);self.pump(app,.02);self.assertFalse(sheet.opened)
        sheet.open();app.request_page(1);self.assertFalse(sheet.opened);self.settle(app)
        sheet.open();sheet.hotkeys.invoke();self.pump(app,.1);self.assertFalse(sheet.opened);self.assertTrue(app.shortcut_window.winfo_exists());self.assertFalse(errors)
