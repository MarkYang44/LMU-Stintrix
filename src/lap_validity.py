"""Game decisions are independent of capture quality and statistic eligibility."""


def evo_flags(valid,invalid):
    # A positive game verdict wins when its two published flags disagree.
    if valid==1:return True
    if valid==0 and invalid==1:return False
    return None


def game_valid(lap):
    return lap.get('game_valid',lap.get('valid'))


def label(lap):
    value=game_valid(lap)
    return '无效' if value is False else '待确认' if value is None else '有效'


def finish_evo(lap):
    legacy=not lap.pop('_invalid') if lap.pop('_known') else None
    explicit=lap.pop('_game_explicit')
    last=lap.pop('_game_valid')
    # A historical OR of two flags cannot prove which game flag was negative.
    # It is still used for old statistic safeguards, never presented as a penalty.
    game=last if explicit else True if lap.pop('_last_invalid')==0 else None
    if explicit:lap.pop('_last_invalid')
    lap.update(valid=game if explicit else legacy,game_valid=game,
        validity_source='evo_game_flags' if explicit else 'evo_legacy_combined',
        validity_disputed=lap.pop('_game_disputed'))
