"""Validate rendered article resources before committing a publication."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit, unquote

class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        key = 'href' if tag in ('a', 'link') else 'src'
        if attrs.get(key):
            self.links.append(attrs[key])

def check_site(destination, urls):
    root = Path(destination).resolve()
    errors = []
    for url in urls:
        article = root / url.lstrip('/') / 'index.html'
        if not article.is_file():
            errors.append(f'발행 페이지가 없습니다: {url}')
            continue
        parser = Links()
        parser.feed(article.read_text(encoding='utf-8'))
        for link in parser.links:
            target = urlsplit(urljoin('https://brothrone.org' + url, link))
            if target.scheme not in ('http', 'https') or target.netloc != 'brothrone.org':
                continue
            if target.path.startswith('/api/'):
                continue
            path = (root / unquote(target.path).lstrip('/')).resolve()
            if root not in path.parents and path != root:
                errors.append(f'잘못된 내부 경로: {link}')
            elif not path.is_file() and not (path / 'index.html').is_file():
                errors.append(f'{url} → 없는 파일/페이지: {target.path}')
    return sorted(set(errors))
