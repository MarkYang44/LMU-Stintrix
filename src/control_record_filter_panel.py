"""Keep record rows visible first while retaining optional filter context."""
from event_filters import DEFAULTS
from control_widgets import px
from i18n import tr


class Panel:
    def __init__(self,page):
        self.page=page;self.filters=page.modes;self.options=self.filters.pack_info();self.options.pop('in',None)
        siblings=self.filters.master.pack_slaves();index=siblings.index(self.filters);self.before=siblings[index+1] if index+1<len(siblings) else None
        self.row=page.buttons['refresh'].master;self.button=page.button(self.row,'filters','筛选条件',self.toggle)
        if not page.context.get('filters_open',False):self.filters.pack_forget()
        self.filters.compact(page.table)
        self.sync()
    def toggle(self):
        opened=not bool(self.filters.winfo_manager());self.page.context['filters_open']=opened
        if opened:self.filters.pack(**self.options,**({'before':self.before} if self.before is not None else {}))
        else:self.filters.pack_forget()
        self.sync()
    def sync(self):
        self.filters.sync_chips()
        count=sum(value!=DEFAULTS.get(key) for key,value in self.filters.state.items() if key not in ('query','sort'))
        title=tr('筛选条件')+(f' · {count}' if count else '')
        if self.button.label!=title:
            self.button.configure(text=title,width=max(px(self.button,135),self.button.font.measure(title)+px(self.button,36)));self.row.event_generate('<Configure>',width=self.row.winfo_width())
        self.button.configure(selected=bool(self.filters.winfo_manager()))
