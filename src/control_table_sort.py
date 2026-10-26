"""Connect table headings to the existing persisted metadata sort IDs."""
PAIRS={'date':(0,1),'type':(2,3),'track':(4,5),'car':(6,7),'mode':(8,9),'lap':(10,18),'result':(11,19)}


def install(table,filters):
    table.sortable=set(PAIRS).intersection(table.columns)
    def sync():
        order=filters.state.get('sort',0)
        table.sort_state=next(((key,pair.index(order)==1) for key,pair in PAIRS.items() if order in pair and key in table.columns),None)
        if order in (0,1) and 'date' in table.columns:table.sort_state=('date',order==0)
        table.header_key=None;table.schedule()
    def sort(key):
        pair=PAIRS[key];order=filters.state.get('sort',0);filters.state['sort']=pair[1] if order==pair[0] else pair[0]
        filters.update_options(filters.items);filters.persist();filters.callback();sync()
    table.sort_command=sort;filters.sort_table=sync;sync()
