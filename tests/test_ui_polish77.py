"""Only the compact guide controls and the interactions changed with them."""
import os,unittest
from unittest.mock import patch
from tests import test_ui_polish69 as helpers


@unittest.skipUnless(os.name=='nt','Native Tk')
class UI(unittest.TestCase):
    app=helpers.UI.app;pump=helpers.UI.pump;settle=helpers.UI.settle
    def guide(self):
        app,root,errors=self.app();app.request_page(5);self.settle(app);return app,root,errors,app.guide_page

    def test_collapsed_filters_remain_removable_and_disclosure_survives_navigation(self):
        app,root,errors,g=self.guide();self.assertFalse(g.filter_fields.winfo_manager());self.assertFalse(g.reset_button.enabled)
        g.select('car:bmw-m4-lmgt3');g.variables['group'].set('LMGT3');g.filter_changed();self.settle(app)
        self.assertTrue(all(car['car_class']=='LMGT3' for car,_ in g.rows));self.assertEqual(list(g.filter_chips.buttons),['group']);self.assertTrue(g.filter_chips.winfo_ismapped())
        g.filter_chips.buttons['group'].invoke();self.settle(app);self.assertEqual(len(g.rows),24);self.assertEqual(g.state['comparison'],['car:bmw-m4-lmgt3'])
        g.toggle_filters();self.pump(app,.05);self.assertTrue(g.filter_fields.winfo_ismapped());app.request_page(0);self.settle(app);app.request_page(5);self.settle(app)
        self.assertTrue(app.guide_page.filter_fields.winfo_ismapped());self.assertFalse((root/'guide_settings.json').exists());self.assertFalse(errors)

    def test_enter_applies_once_and_empty_recovery_keeps_filters_and_comparison(self):
        app,root,errors,g=self.guide();app.root.lift();g.search_entry.focus_force();self.pump(app,.05)
        with patch.object(g,'render',wraps=g.render) as render:
            for value in ('B','BM','BMW'):g.variables['query'].set(value)
            g.search_entry.event_generate('<Return>');self.assertEqual(len(g.rows),2);self.assertIsNone(g.search_field.pending);self.settle(app);self.pump(app,.12);self.assertEqual(render.call_count,1)
        g.select('car:bmw-m4-lmgt3');g.variables['group'].set('LMGT3');g.filter_changed();g.variables['query'].set('no such guide car');g.search_field.flush();self.settle(app);self.assertFalse(g.rows)
        g.empty_action.invoke();self.settle(app);self.assertEqual(g.state['query'],'');self.assertEqual(g.state['group'],'LMGT3');self.assertTrue(g.rows);self.assertEqual(g.state['comparison'],['car:bmw-m4-lmgt3']);self.assertFalse(errors)

    def test_selected_chips_remove_only_one_item_and_keep_browse_context_in_small_english_ui(self):
        app,root,errors,g=self.guide();chosen=['car:bmw-m4-lmgt3','car:ferrari-296-lmgt3','car:porsche-911-gt3-r']
        for key in chosen:g.select(key)
        g.turn(2);self.settle(app);widgets=g.results.winfo_children();g.selection_chips.buttons[chosen[1]].invoke()
        self.assertEqual(g.state['comparison'],[chosen[0],chosen[2]]);self.assertEqual(g.state['page'],2);self.assertEqual(g.results.winfo_children(),widgets)
        g.compare();self.settle(app);g.selection_chips.buttons[chosen[2]].invoke();self.settle(app);self.assertEqual(g.state['mode'],'browse');self.assertEqual(g.state['page'],2);self.assertEqual(g.state['comparison'],[chosen[0]])
        app.set_theme('light');app.toggle_language();app.root.geometry('1060x700');self.pump(app,.25);g=app.guide_page
        self.assertIn('Selected for comparison',g.selected_label.cget('text'));self.assertEqual(g.state['comparison'],[chosen[0]])
        for button in g.selection_chips.buttons.values():self.assertLessEqual(button.winfo_x()+button.winfo_width(),g.selection_chips.winfo_width());self.assertLessEqual(button.font.measure(button.label)+36*button.s,button.winfo_width()+1)
        self.assertFalse(errors)
