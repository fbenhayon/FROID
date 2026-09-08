"""Verificação local de estrutura e regressões editoriais do site.

Execute da raiz: python docs/verificar-site.py
Não acessa produção nem altera arquivos.
"""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, unquote
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / 'froid-site'
VOID = set('area base br col embed hr img input link meta param source track wbr'.split())

class Page(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.ids=set(); self.links=[]; self.errors=[]; self.stack=[]
        self.feed(text)
        if self.stack: self.errors.append('unclosed: '+str(self.stack))

    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        if attrs.get('id'):
            if attrs['id'] in self.ids: self.errors.append('duplicate id: '+attrs['id'])
            self.ids.add(attrs['id'])
        if tag=='a' and attrs.get('href'): self.links.append(attrs['href'])
        if tag not in VOID: self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID: self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag in VOID: return
        if not self.stack or self.stack[-1]!=tag:
            self.errors.append('closing '+tag+' after '+str(self.stack[-3:]))
        if tag in self.stack:
            self.stack=self.stack[:len(self.stack)-1-self.stack[::-1].index(tag)]

def verify():
    pages={p:Page(p.read_text(encoding='utf-8')) for p in SITE.rglob('*.html')}
    errors=[]; links=0; scripts=0
    for p,page in pages.items():
        errors.extend(str(p.relative_to(ROOT))+': '+e for e in page.errors)
        for href in page.links:
            u=urlsplit(href)
            if u.scheme or u.netloc or not (u.path.endswith('.html') or (not u.path and u.fragment)): continue
            target=(p.parent/unquote(u.path)).resolve() if u.path else p
            links+=1
            if target not in pages: errors.append(str(p.relative_to(SITE))+': missing '+href)
            elif u.fragment and unquote(u.fragment) not in pages[target].ids:
                errors.append(str(p.relative_to(SITE))+': missing anchor '+href)
        text=p.read_text(encoding='utf-8')
        for bad in ('Ã§','Ã£','â€','\ufffd'):
            if bad in text: errors.append(str(p.relative_to(SITE))+': encoding '+repr(bad))
        for body in re.findall(r'<script\b[^>]*>(.*?)</script>',text,re.S):
            if not body.strip(): continue
            with tempfile.TemporaryDirectory(prefix='froid-site-check-') as tmp:
                js=Path(tmp)/'inline.js'; js.write_text(body,encoding='utf-8')
                result=subprocess.run(['node','--check',str(js)],capture_output=True,text=True)
                if result.returncode: errors.append(str(p.relative_to(SITE))+': '+result.stderr)
            scripts+=1
    nav=(SITE/'site-assets/script.js').read_text(encoding='utf-8')
    mapping=re.search(r'var NAV_SECOES = (\{.*?\n\});',nav,re.S).group(1)
    import json
    menu=0
    for name,sections in json.loads(mapping).items():
        for id,_ in sections:
            menu+=1
            if id not in pages[SITE/name].ids: errors.append('NAV_SECOES: '+name+'#'+id)
    for p in SITE.rglob('demonstracao.html'):
        text=p.read_text(encoding='utf-8')
        for forbidden in ('Math.random','ipmCanvas','P-2043','playBtn'):
            if forbidden in text: errors.append(str(p)+': fabricated demo '+forbidden)
    for p in SITE.rglob('froid-explica.html'):
        text=p.read_text(encoding='utf-8')
        for forbidden in ('1,2 tri','1.2 trillion','1,2 mille','Predição de resposta','Prediction of therapeutic','Predicción de respuesta'):
            if forbidden in text: errors.append(str(p)+': unsupported claim '+forbidden)
    print(f'Pages: {len(pages)}; local links: {links}; menu anchors: {menu}; inline scripts: {scripts}; failures: {len(errors)}')
    for error in errors: print(error)
    return len(errors)

if __name__=='__main__':
    raise SystemExit(bool(verify()))
