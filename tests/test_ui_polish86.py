"""Guide list mode: every entry at once, full cards opened in place."""
import os,unittest
from tests import test_ui_polish69 as helpers


@unittest.skipUnless(os.name=='nt','Native Tk')
class UI(unittest.TestCase):
    app=helpers.UI.app;pump=helpers.UI.pump;settle=helpers.UI.settle

    def listing(self,app,page=4):
        app.request_page(page);self.settle(app);g=app.guide_page;switch=g.layout_switch
        left,right=switch.spans[1];switch.event_generate('<Button-1>',x=round((left+right)/2),y=10);self.settle(app)
        return app.guide_page

    def test_list_shows_every_entry_and_opens_full_cards_in_place(self):
        app,root,errors=self.app();g=self.listing(app)
        self.assertEqual(g.state['layout'],'list');self.assertEqual(len(g.list_rows),len(g.rows));self.assertEqual(len(g.rows),18)
        self.assertFalse(any(button.enabled for pair in g.pagers for button in pair));self.assertEqual(g.page_number.get(),'全部 18')
        row=g.list_rows[1]
        row.toggle();self.pump(app,.1);self.assertEqual(g.state['list_open'],[row.guide_slug])
        opened=[w for w in row.master.winfo_children() if not hasattr(w,'guide_slug') and w.winfo_manager() and w.winfo_children()]
        self.assertEqual(len(opened),1);self.assertGreater(opened[0].winfo_rooty(),row.winfo_rooty())
        row.toggle();self.pump(app,.05);self.assertEqual(g.state['list_open'],[])
        row.focus_force();self.pump(app,.05);row.event_generate('<Down>');self.pump(app,.05);self.assertIs(app.root.focus_get(),g.list_rows[2])
        g.list_rows[2].event_generate('<Return>');self.pump(app,.1);self.assertEqual(g.state['list_open'],[g.list_rows[2].guide_slug]);self.assertFalse(errors)

    def test_search_narrows_the_list_and_a_single_match_opens(self):
        app,root,errors=self.app();g=self.listing(app)
        g.variables['query'].set('Bahrain');g.search_field.flush();self.settle(app);g=app.guide_page
        self.assertEqual([row.guide_slug for row in g.list_rows],['bahrain']);self.assertIn('bahrain',g.state['list_open'])
        g.variables['query'].set('');g.search_field.flush();self.settle(app);g=app.guide_page
        switch=g.layout_switch;left,right=switch.spans[0];switch.event_generate('<Button-1>',x=round((left+right)/2),y=10);self.settle(app);g=app.guide_page
        self.assertEqual(g.state['layout'],'cards');self.assertEqual(g.card_count,3);self.assertTrue(g.pagers[0][1].enabled);self.assertEqual(g.page_number.get(),'1 / 6');self.assertFalse(errors)

    def test_car_catalog_lists_cars_with_their_class(self):
        app,root,errors=self.app();g=self.listing(app,5)
        self.assertEqual(len(g.list_rows),24);texts=[w.cget('text') for w in g.list_rows[0].winfo_children()]
        self.assertTrue(any(text in ('LMGT3','Hypercar') for text in texts));self.assertFalse(errors)
