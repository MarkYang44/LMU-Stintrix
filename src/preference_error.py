"""Validation locations for presentation; remains compatible with ValueError."""


class PreferenceError(ValueError):
    def __init__(self,message,*fields,limits=None):
        super().__init__(message);self.fields=fields;self.limits=limits


def read_object(path):
    """Read before updating settings; never replace malformed existing content."""
    import json
    try:text=path.read_text(encoding='utf-8-sig')
    except FileNotFoundError:return {}
    try:value=json.loads(text)
    except (ValueError,UnicodeError) as error:raise PreferenceError('设置文件无法读取，原文件已保留') from error
    if not isinstance(value,dict):raise PreferenceError('设置文件格式无效，原文件已保留')
    return value
