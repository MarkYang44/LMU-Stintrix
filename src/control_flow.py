"""Wrap action rows at their natural translated widths without shrinking captions."""
from control_widgets import px


def uninstall(parent):
    token=getattr(parent,'flow_binding',None)
    if token:parent.unbind('<Configure>',token);parent.flow_binding=None


def install(parent):
    uninstall(parent)
    def arrange(event):
        if event.widget is not parent:return
        x=y=height=0;gap=px(parent,8)
        for child in parent.winfo_children():
            child.pack_forget();width=child.winfo_reqwidth();h=child.winfo_reqheight()
            if x and x+width>event.width:y+=height+gap;x=height=0
            child.place(x=x,y=y,width=min(event.width,width),height=h);x+=width+gap;height=max(height,h)
        parent.pack_propagate(False);parent.configure(height=max(1,y+height))
    parent.flow_binding=parent.bind('<Configure>',arrange,add='+')
