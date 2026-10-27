"""Algorithm-owned lap caches; UI/application releases do not change data rules."""
KINDS=('scan','export')
REVISION=1  # Bump when lap selection, curve/CSV semantics or schema changes.
LEGACY_APPS=('0.3.15','0.3.16')  # Full output equality verified before admission.


def signature(folder,kind):
    if kind not in KINDS:raise ValueError('Unknown lap cache kind')
    from comparison_cache import source
    return dict(format='stintrix.lap-cache',version=3,kind=kind,revision=REVISION,source=source(folder))


def compatible(saved,expected):
    if saved==expected:return True
    # Older envelopes still require their original digest/output checks. Only
    # these known equivalent releases can enter revision 1 without rescanning.
    return (isinstance(saved,dict) and set(saved)=={'version','app','source'} and saved['version']==2
        and saved['app'] in LEGACY_APPS and expected.get('format')=='stintrix.lap-cache'
        and expected.get('version')==3 and expected.get('kind') in KINDS and expected.get('revision')==1
        and saved['source']==expected.get('source'))
