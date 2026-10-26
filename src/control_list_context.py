"""Context actions retain multi-selection and restore keyboard focus to the list."""
from control_motion import keyboard_action


def install(table,menu,changed=lambda:None):
    def mouse(event):
        iid=table.at(event)
        if iid is None:menu.close(False);return 'break'
        table.tooltip.hide();table.viewport.focus_set()
        if iid not in table.selection():table.selection_set((iid,))
        table.cursor=iid;cell=table.cell_at(event)
        if cell:table.focus_column=cell[1]
        changed();return menu.open((event.x_root-menu.owner.winfo_rootx(),event.y_root-menu.owner.winfo_rooty()),return_focus=table.viewport)
    def key(_):
        chosen=table.selection()
        if not chosen:return 'break'
        table.cursor=table.cursor if table.cursor in chosen else chosen[0];table.tooltip.hide();changed()
        y=max(0,min(table.viewport.winfo_height()-table.rowheight,table.order.index(table.cursor)*table.rowheight-table.offset))
        position=(table.viewport.winfo_rootx()-menu.owner.winfo_rootx()+20,table.viewport.winfo_rooty()-menu.owner.winfo_rooty()+y+table.rowheight)
        return keyboard_action(table,lambda:menu.open(position,return_focus=table.viewport))
    table.viewport.bind('<Button-3>',mouse);table.viewport.bind('<Menu>',key);table.viewport.bind('<Shift-F10>',key)
