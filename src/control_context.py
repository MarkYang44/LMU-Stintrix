"""Bounded, in-memory browsing context; no racing records are modified."""
class BrowseMemory:
    def __init__(self):self.states={}
    def capture(self,app):
        active=getattr(getattr(app,'pages',None),'active',None)
        if active is None or not active.frame.winfo_exists() or not active.frame.winfo_manager():return
        state=self.states.setdefault(app.page,{})
        state['scroll']=app.scroll.yview()[0]
        if app.page in (1,3) and app.tree is not None and app.tree.winfo_exists():
            state.update(query=app.search.get(),selected=[app.items[int(i)]['folder'] for i in app.tree.selection() if i.isdigit() and int(i)<len(app.items)],offset=app.tree.offset,xoffset=app.tree.xoffset)
        if app.page==3:
            from control_renderer import capture
            capture(app);state['drafts']={}
        filters=getattr(app,'review_filters',None)
        if filters is not None and filters.winfo_exists():state['advanced']=bool(filters.advanced.winfo_manager())
    def query(self,page):return self.states.get(page,{}).get('query','')
    def selected(self,page,items):
        folders=set(self.states.get(page,{}).get('selected',[]))
        return [str(i) for i,item in enumerate(items) if item['folder'] in folders]
    def restore(self,app,table=False):
        state=self.states.get(app.page,{})
        for key,value in state.get('drafts',{}).items():
            if hasattr(app,key):getattr(app,key).set(value)
        app.root.update_idletasks();app.scroll.yview_moveto(state.get('scroll',0))
        if table and app.tree is not None:
            app.tree.scroller.move(state.get('offset',0));app.tree.xoffset=state.get('xoffset',0);app.tree.schedule()
