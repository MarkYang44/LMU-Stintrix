"""GUI-thread page transitions and rebuild snapshots, independent of HUD commands."""
from dataclasses import dataclass
import tkinter as tk
from control_theme import T
from simulator_profiles import profile


@dataclass
class InterfaceState:
    page:int
    geometry:str
    scroll:float
    variables:dict
    query:str
    selected:tuple
    table_offset:int

    @classmethod
    def capture(cls,app):
        return cls(app.page,app.root.geometry(),app.scroll.yview()[0],
            {name:value.get() for name,value in vars(app).items() if isinstance(value,tk.Variable)},
            app.search.get() if app.tree else '',app.tree.selection() if app.tree else (),
            app.tree.offset if app.tree else 0)

    def restore(self,app):
        for name,value in self.variables.items():
            variable=getattr(app,name,None)
            if isinstance(variable,tk.Variable):variable.set(value)
        if app.tree:app.search.set(self.query);app.populate(self.selected)
        app.root.update_idletasks();app.scroll.yview_moveto(self.scroll)
        if app.tree:app.tree.scroller.move(self.table_offset)


def rebuild_interface(app):
    snapshot=InterfaceState.capture(app)
    from control_forms import capture
    app.form_drafts=capture(app.pages,app.form_drafts)
    app.browsing.capture(app)
    app.clear_toolbar();app.pages.dispose()
    app.shell.motion.cancel();app.shell.scroller.cancel();app.shell.navigation.motion.cancel()
    app.shell.detach();app.shell.side.destroy();app.shell.main.destroy();app.root.configure(bg=T.BG)
    app.build_shell();app.root.geometry(snapshot.geometry);app.show_page(snapshot.page)
    snapshot.restore(app)


def show_page(app,index,progressive=False):
    app.browsing.capture(app)
    if not app.shell.covering:app.shell.cover_page()
    app.clear_toolbar();app.pages.cancel_request()
    app.page=index;app.restore_list_context=True;app.progressive=progressive
    app.scan_generation+=1;app.tree=None;app.guide_page=None
    app.shell.scroller.cancel()
    app.title.configure(text=app.page_titles[index]);app.subtitle.configure(text=app.page_subtitles[index]);app.scroll.yview_moveto(0)
    if app.shell.navigation.selected!=index:app.shell.select(index)
    builder=(app.run_page,app.review_page,app.settings_page,app.data_page,app.tracks_page,app.cars_page,app.records_page)[index]
    if profile(app.simulator).catalogue=='official':
        from evo_control import builder_for
        builder=builder_for(app,index,builder)
    app.pages.mount(index,builder,progressive)
