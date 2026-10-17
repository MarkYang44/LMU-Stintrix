"""Check bilingual homepage structure, relative links and paired real captures."""
from html.parser import HTMLParser
from pathlib import Path
import re
from urllib.parse import unquote,urlsplit

ROOT=Path(__file__).resolve().parents[1]


def headings(text):
    return re.findall(r'^(#{1,6}) (.+)$',text,re.M)


def anchors(text):
    return {re.sub(r'[^\w\- ]','',re.sub(r'[`*]','',title).lower()).replace(' ','-') for _,title in headings(text)}


class Links(HTMLParser):
    def __init__(self):super().__init__();self.urls=[];self.images=[]
    def handle_starttag(self,tag,attributes):
        attr=dict(attributes)
        for key in ('href','src','srcset'):
            if key in attr:self.urls.append(attr[key])
        if tag=='img' and attr.get('src','').startswith('docs/screenshots/'):self.images.append(attr['src'])


def inspect(path):
    text=path.read_text(encoding='utf8');parser=Links();parser.feed(text)
    urls=parser.urls+re.findall(r'\]\(([^\s)]+)',text)
    for url in urls:
        parts=urlsplit(url)
        if parts.scheme or parts.netloc:continue
        target=(path.parent/unquote(parts.path)).resolve() if parts.path else path
        assert target.is_relative_to(ROOT) and target.is_file(),f'{path.name}: missing relative link {url}'
        if parts.fragment and target.suffix=='.md':assert unquote(parts.fragment) in anchors(target.read_text('utf8')),f'{path.name}: missing anchor {url}'
    assert sum(level=='#' for level,_ in headings(text))==1,f'{path.name}: expected one H1'
    assert len(parser.images)==4,f'{path.name}: expected four screenshot views'
    return text,parser.images,len(urls)


def main():
    from PIL import Image
    from tools.readme_assets import README_ASSETS
    en,images_en,links_en=inspect(ROOT/'README.md');zh,images_zh,links_zh=inspect(ROOT/'README.zh-CN.md')
    assert [len(level) for level,_ in headings(en)]==[len(level) for level,_ in headings(zh)],'Heading hierarchy differs'
    assert [Path(p).name for p in images_en]==[Path(p).name for p in images_zh],'Screenshot order differs'
    assert len(re.findall(r'^- ',en,re.M))==len(re.findall(r'^- ',zh,re.M)),'Feature bullet counts differ'
    assert set(images_en+images_zh)==set(README_ASSETS),'Capture allowlist differs from homepage images'
    for a,b in zip(images_en,images_zh):
        assert '/en/' in a and '/zh-CN/' in b,'Wrong screenshot locale'
        with Image.open(ROOT/a) as first,Image.open(ROOT/b) as second:
            assert first.format==second.format=='WEBP' and first.size==second.size,'Capture formats or dimensions differ'
            expected=(1280,450) if Path(a).name=='input-hud.webp' else (1280,900)
            assert first.size==expected,(a,first.size)
        for name in (a,b):assert (ROOT/name).stat().st_size==README_ASSETS[name],'Reviewed capture size differs'
    print(f'PASS: matching bilingual hierarchy and image order; {links_en+links_zh} links; 4 real screenshot pairs')
    print(f'Homepage source sizes: English {len(en.encode())} bytes; Chinese {len(zh.encode())} bytes')


if __name__=='__main__':
    import sys
    sys.path.insert(0,str(ROOT))
    main()
