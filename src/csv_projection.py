"""Project parsed CSV rows in C; retain DictReader's short/missing cell rules."""
from operator import itemgetter


def projector(fields,columns):
    positions={name:i for i,name in enumerate(fields)}
    indices=[positions.get(name) for name in columns]
    def fallback(row):
        return tuple(row[i] if i is not None and i<len(row) else None if i is not None else '' for i in indices)
    if not indices:return lambda row:()
    if None in indices:return fallback
    width=max(indices)+1
    take=itemgetter(*indices)
    if len(indices)==1:
        def select(row):return (take(row),) if len(row)>=width else fallback(row)
    else:
        def select(row):return take(row) if len(row)>=width else fallback(row)
    if indices==list(range(len(indices))) and len(positions)==len(indices):
        # A complete, uniquely named row is already in the requested order.
        # Sparse/extra cells still use the original DictReader-compatible path.
        def identity(row):return tuple(row) if len(row)==width else select(row)
        return identity
    return select
