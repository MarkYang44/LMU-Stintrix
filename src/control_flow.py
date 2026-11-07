"""Wrap action rows at their natural translated widths without shrinking captions."""
from control_widgets import px


def uninstall(parent):
    token=getattr(parent,'flow_binding',None)
    if token:parent.unbind('<Configure>',token);parent.flow_binding=None


def lines(children,available,gap):
    """Group (child,width,height) into wrapped lines at natural widths."""
    rows=[];x=0
    for child in children:
        width=child.winfo_reqwidth()
        if not rows or (x and x+width>available):rows.append([]);x=0
        rows[-1].append((child,width,child.winfo_reqheight()));x+=width+gap
    return rows


def place(rows,available,gap):
    """Centre captions, switches and buttons on each line's tallest control."""
    y=0
    for index,row in enumerate(rows):
        if index:y+=gap
        height=max(h for *_,h in row);x=0
        # A stretch child (a toolbar search field) takes the line's spare room.
        spare=max(0,available-sum(width for _,width,_ in row)-gap*(len(row)-1))
        for child,width,h in row:
            if getattr(child,'flow_stretch',False):width+=spare;spare=0
            child.place(x=x,y=y+(height-h)//2,width=min(available,width),height=h);x+=width+gap
        y+=height
    return y


def install(parent):
    uninstall(parent)
    def arrange(event):
        if event.widget is not parent:return
        gap=px(parent,8);children=parent.winfo_children()
        for child in children:child.pack_forget()
        height=place(lines(children,event.width,gap),event.width,gap)
        parent.pack_propagate(False);parent.configure(height=max(1,height))
    parent.flow_binding=parent.bind('<Configure>',arrange,add='+')
