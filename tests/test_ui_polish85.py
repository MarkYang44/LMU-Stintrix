"""Side-by-side run cards end on one line, a live HUD preview fills the spare room, F5 refreshes sessions."""
import os,time,unittest
from unittest.mock import patch
from tests import test_ui_polish69 as helpers


def wait(root,condition,seconds=3):
    deadline=time.monotonic()+seconds
    while not condition() and time.monotonic()<deadline:root.update();time.sleep(.005)
    return condition()


@unittest.skipUnless(os.name=='nt','Native Tk')
class UI(unittest.TestCase):
    app=helpers.UI.app;pump=helpers.UI.pump;settle=helpers.UI.settle

    def cards(self,app):
        preview=app.hud_preview;left=preview.master.master;grid=left.master
        return grid,[card for card in grid.cards]

    def test_side_by_side_cards_share_one_height_and_the_preview_takes_the_room(self):
        app,root,errors=self.app();app.root.geometry('1600x1000');self.settle(app);self.pump(app,.2)
        grid,cards=self.cards(app);self.assertTrue(grid.wide);self.assertEqual(len(cards),2)
        self.assertTrue(wait(app.root,lambda:abs(cards[0].winfo_height()-cards[1].winfo_height())<=1))
        self.assertEqual(cards[0].winfo_rooty(),cards[1].winfo_rooty())
        # The shorter card is the one stretched; when it is the display card, its preview takes the room.
        naturals=[card.natural() for card in cards];self.assertEqual([card.floor for card in cards],[max(naturals)]*2)
        if naturals[0]<naturals[1]:self.assertGreater(app.hud_preview.winfo_height(),app.hud_preview.winfo_reqheight())
        app.root.geometry('1060x700');self.pump(app,.4)
        self.assertFalse(grid.wide);self.assertEqual([card.floor for card in cards],[0,0]);self.assertEqual(cards[0].winfo_height(),cards[0].natural());self.assertFalse(errors)

    def test_preview_follows_the_choices_and_opens_the_layout_editor(self):
        app,root,errors=self.app();self.settle(app);preview=app.hud_preview;app.root._motion_keyboard_until=time.perf_counter()+5
        self.assertEqual((preview.header,preview.panel,preview.cycles),(1.,1.,2.))
        app.mode_label.set('纯净 · 仅曲线');app.window.set('20');self.pump(app,.05)
        self.assertEqual((preview.header,preview.panel,preview.cycles),(0.,0.,4.))
        texts=[preview.itemcget(i,'text') for i in preview.find_all() if preview.type(i)=='text']
        self.assertIn('画面预览 · 纯净 · 仅曲线',texts);self.assertIn('20 s',texts)
        app.mode_label.set('纯净 · 曲线 + 踏板 / 方向盘');self.pump(app,.05);self.assertEqual((preview.header,preview.panel),(0.,1.))
        preview.event_generate('<Button-1>',x=20,y=20);self.pump(app,.2)
        self.assertTrue(getattr(app,'layout_window',None) is not None and app.layout_window.winfo_exists());self.assertFalse(errors)

    def test_f5_refreshes_the_review_list_only_while_it_is_shown(self):
        app,root,errors=self.app(True);app.request_page(1);self.settle(app,lambda:bool(app.tree and app.tree.get_children()))
        with patch.object(app,'refresh') as refresh:
            app.root.event_generate('<F5>');self.assertEqual(refresh.call_count,1)
            app.request_page(0);self.settle(app);app.root.event_generate('<F5>');self.assertEqual(refresh.call_count,1)
        self.assertFalse(errors)
