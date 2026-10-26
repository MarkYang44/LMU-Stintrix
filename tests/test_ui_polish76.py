"""Focused checks for visible filter context and sequential record browsing."""
import json,os,unittest
from unittest.mock import patch
from tests import test_ui_polish64 as fixtures


@unittest.skipUnless(os.name=='nt','Native Tk')
class UI(unittest.TestCase):
    app=fixtures.BestUI.app;pump=fixtures.BestUI.pump;mount=fixtures.BestUI.mount
    def test_collapsed_conditions_remove_individually_and_clear_keeps_search_and_sort(self):
        app,root,errors=self.app();p,_=self.mount(app,root);f=p.modes
        p.query.set('BMW');p.search_field.flush();f.state.update(vehicle_class='LMGT3',mode='unknown',sort=5);f.update_options(p.entries);p.populate_best();self.pump(app,.1)
        self.assertFalse(f.winfo_manager());self.assertTrue(f.chips.winfo_ismapped());self.assertIs(f.chips.pack_info()['in'],f.master)
        next(w for w in f.chip_widgets if '参赛方式' in w.label).invoke();self.assertEqual(f.state['mode'],'');self.assertEqual(f.state['vehicle_class'],'LMGT3')
        next(w for w in f.chip_widgets if w.label=='清除条件').invoke();self.assertEqual(p.query.get(),'BMW');self.assertEqual(f.state['sort'],5);self.assertEqual(f.state['vehicle_class'],'');self.assertTrue(p.rows)
        saved=json.loads(f.path.read_text())['states'][f.key];self.assertEqual(saved['query'],'BMW');self.assertEqual(saved['sort'],5)
        p.toggle_filters();self.pump(app,.05);self.assertIs(f.chips.pack_info()['in'],f);p.toggle_filters();self.pump(app,.05);self.assertIs(f.chips.pack_info()['in'],f.master);self.assertFalse(errors)

    def test_neighbors_follow_filtered_order_keep_detail_position_and_menu_uses_current_record(self):
        app,root,errors=self.app();p,_=self.mount(app,root);p.query.set('BMW');p.search_field.flush();p.fixed['details'].invoke();self.pump(app,.1)
        keys=p.table.get_children();p.table.selection_set((keys[0],));self.pump(app,.05);self.assertFalse(p.buttons['previous'].enabled);position=app.scroll.yview()[0]
        with patch('control_records.detail',side_effect=fixtures.detail),patch.object(p.exporter,'create') as opened,patch('control_record_browser.os.startfile') as folder:
            for key in keys[1:]:
                p.buttons['next'].invoke();self.assertEqual(p.table.selection(),(key,));self.assertEqual(p.selected,p.lookup[key])
            self.pump(app,.2);self.assertFalse(p.buttons['next'].enabled);p.buttons['next'].invoke();self.assertEqual(p.table.selection(),(keys[-1],))
            p.buttons['curve'].invoke();opened.assert_called_once_with(p,p.selected)
            p.menu.invoke('folder');folder.assert_called_once_with(str(p.selected['folder']))
        self.assertAlmostEqual(app.scroll.yview()[0],position,places=2);self.assertFalse(p.buttons['retry'].winfo_manager());self.assertTrue(p.table.viewport.bind('<Button-3>'));self.assertTrue(p.table.viewport.bind('<Shift-F10>'))
        p.buttons['list'].invoke();self.pump(app,.08);self.assertEqual(p.table.selection(),(keys[-1],));self.assertFalse(errors)

    def test_shared_compact_filters_survive_language_theme_and_page_disposal(self):
        app,root,errors=self.app(True);app.show_page(3);self.pump(app,.3);app.data_tasks.select('packages');browser=app.data_browser;f=browser.filters
        f.state['mode']='single';f.update_options(app.items);f.callback();self.pump(app,.1);self.assertFalse(f.winfo_manager());self.assertTrue(f.chips.winfo_ismapped())
        app.set_theme('light');app.toggle_language();app.root.geometry('1060x700');self.pump(app,.3);browser=app.data_browser;f=browser.filters
        self.assertTrue(f.chips.winfo_ismapped());self.assertTrue(any('Participation' in w.cget('text') for w in f.chip_widgets))
        browser.toggle_filters();self.pump(app,.05);self.assertIs(f.chips.pack_info()['in'],f);browser.toggle_filters();self.pump(app,.05);self.assertIs(f.chips.pack_info()['in'],f.master)
        for w in f.chip_widgets:self.assertLessEqual(w.winfo_x()+w.winfo_width(),f.chips.winfo_width())
        old=f.chips;app.personal_record_view='history';app.show_page(6);self.pump(app,.3);self.assertFalse(old.winfo_exists())
        page=app.record_loaders['history'].page;f=page.modes;f.state['mode']='single';f.update_options(page.entries);page.refresh_rows();self.pump(app,.1)
        self.assertTrue(f.chips.winfo_ismapped());page.filter_panel.toggle();self.pump(app,.05);self.assertIs(f.chips.pack_info()['in'],f);page.filter_panel.toggle();self.pump(app,.05);self.assertIs(f.chips.pack_info()['in'],f.master);self.assertFalse(errors)
