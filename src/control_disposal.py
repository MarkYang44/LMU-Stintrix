"""Retire page-owned Tk variables on the GUI thread, never in worker GC."""
import tkinter as tk


def release(page,owner):
    variables={}
    # Variables marked shared belong to the shell (theme, language); a page
    # control that mirrors them must not retire them with the page.
    def keep(value):
        if isinstance(value,tk.Variable) and not getattr(value,'shared',False):variables[id(value)]=value
        elif isinstance(value,dict):
            for item in value.values():
                if isinstance(item,tk.Variable) and not getattr(item,'shared',False):variables[id(item)]=item
    def visit(widget):
        for value in vars(widget).values():keep(value)
        for child in widget.winfo_children():visit(child)
    if page.frame.winfo_exists():visit(page.frame)
    for value in page.attributes.values():keep(value)
    for form in page.forms.values():keep(form)
    if page.frame.winfo_exists():page.frame.destroy()
    for value in variables.values():
        if value._tk is not None:value.__del__();value._tk=None
    for name,value in list(vars(owner).items()):
        if isinstance(value,tk.Variable) and id(value) in variables:delattr(owner,name)
