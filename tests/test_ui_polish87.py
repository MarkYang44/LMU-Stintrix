"""Header theme and language toggles show the current state as segmented choices."""
import os,unittest
from tests import test_ui_polish69 as helpers


@unittest.skipUnless(os.name=='nt','Native Tk')
class UI(unittest.TestCase):
    app=helpers.UI.app;pump=helpers.UI.pump;settle=helpers.UI.settle

    def click(self,control,index):
        left,right=control.spans[index];control.event_generate('<Button-1>',x=round((left+right)/2),y=8)

    def test_theme_and_language_read_their_current_state_and_switch_with_one_click(self):
        import i18n
        from control_theme import T
        from control_widgets import Segmented
        app,root,errors=self.app();self.settle(app);shell=app.shell
        self.assertIsInstance(shell.theme_button,Segmented);self.assertEqual((shell.theme_var.get(),shell.language_var.get()),(T.mode,i18n.language))
        self.assertEqual(shell.theme_var.get(),'dark');self.click(shell.theme_button,0);self.pump(app,.05);self.assertEqual(T.mode,'dark')
        self.click(shell.theme_button,1);self.pump(app,.2);self.assertEqual((T.mode,shell.theme_var.get()),('light','light'))
        app.set_theme('dark');self.pump(app,.05);self.assertEqual(shell.theme_var.get(),'dark')
        self.click(shell.language_button,1);self.pump(app,.4);self.assertEqual(i18n.language,'en')
        self.assertEqual(app.shell.language_var.get(),'en');self.assertEqual(app.shell.theme_var.get(),'dark')
        self.click(app.shell.language_button,0);self.pump(app,.4);self.assertEqual(i18n.language,'zh');self.assertFalse(errors)

    def test_rebuilt_header_releases_its_variables_on_the_gui_thread(self):
        # Worker-thread garbage collection of Tk variables stalls Tcl for a second each.
        app,root,errors=self.app();self.settle(app);old=(app.shell.theme_var,app.shell.language_var)
        app.toggle_language();self.pump(app,.3);self.assertTrue(all(variable._tk is None for variable in old))
        app.palette.open();query=app.palette.query;app.palette.close();self.assertIsNone(query._tk)
        app.toggle_language();self.pump(app,.3);self.assertFalse(errors)
