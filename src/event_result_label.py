"""Concise confirmed class result; never fall back to overall/observed ranks."""
from podium_records import rank


def label(facets):
    if facets.get('trust') not in ('official','telemetry'):return '—'
    outcome=facets.get('outcome')
    if outcome in ('dnf','dq'):return outcome.upper()
    if facets.get('phase') not in ('Race','Qualify') or outcome!='finished':return '—'
    value=rank(facets.get('finish_class'))
    return 'P'+str(value) if value else '—'
