#!/usr/bin/env python3
"""读毛选 — 毛泽东选集在线阅读服务"""
import os
import json
import re
import gzip
import mimetypes
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from annotations import get_annotation, ANNOTATIONS, get_cards, get_all_card_ids

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONTENT_DIR = os.path.join(BASE_DIR, 'MaoZeDongAnthology')
STATIC_DIR = BASE_DIR

NUM_PREFIX = re.compile(r'^\d+[\s\-]+')

COMPRESSIBLE = {
    'text/html', 'text/css', 'text/javascript',
    'application/javascript', 'application/json',
    'image/svg+xml',
}

STATIC_WHITELIST = {
    '.html', '.css', '.js', '.json', '.svg', '.png', '.ico',
    '.jpg', '.jpeg', '.gif', '.webp', '.woff', '.woff2', '.ttf',
    '.webmanifest',
}


def clean_name(s):
    return NUM_PREFIX.sub('', s)


def build_toc():
    volumes = []
    article_id = 0
    article_map = {}

    vol_dirs = sorted(
        d for d in os.listdir(CONTENT_DIR)
        if os.path.isdir(os.path.join(CONTENT_DIR, d))
        and re.match(r'^\d{3}', d)
        and '合并' not in d
    )

    for vi, vol_dir in enumerate(vol_dirs):
        vol_path = os.path.join(CONTENT_DIR, vol_dir)
        vol_obj = {'name': clean_name(vol_dir), 'sections': [], 'articles': []}

        try:
            entries = sorted(os.listdir(vol_path))
        except OSError:
            continue

        sub_dirs = [e for e in entries if os.path.isdir(os.path.join(vol_path, e))]
        md_files = [e for e in entries if e.endswith('.md')]

        if sub_dirs:
            for sub_dir in sorted(sub_dirs):
                sub_path = os.path.join(vol_path, sub_dir)
                section = {'name': clean_name(sub_dir), 'articles': []}
                try:
                    sub_mds = sorted(f for f in os.listdir(sub_path) if f.endswith('.md'))
                except OSError:
                    continue
                for md in sub_mds:
                    article_id += 1
                    title = clean_name(md[:-3])
                    article_map[article_id] = os.path.join(sub_path, md)
                    section['articles'].append({'id': article_id, 'title': title})
                vol_obj['sections'].append(section)

        for md in md_files:
            article_id += 1
            title = clean_name(md[:-3])
            article_map[article_id] = os.path.join(vol_path, md)
            vol_obj['articles'].append({'id': article_id, 'title': title})

        volumes.append(vol_obj)

    return volumes, article_map


def build_search_index(article_map, toc):
    """Build a flat search index: [{id, title, snippet}] for full-text search."""
    index = []
    title_map = {}
    for v in toc:
        for s in v.get('sections', []):
            for a in s['articles']:
                title_map[a['id']] = a['title']
        for a in v.get('articles', []):
            title_map[a['id']] = a['title']

    for aid, path in article_map.items():
        try:
            with open(path, encoding='utf-8') as f:
                text = f.read()
            text_clean = re.sub(r'[#*\-_>\[\]()]+', ' ', text)
            text_clean = re.sub(r'\s+', ' ', text_clean).strip()
            index.append({
                'id': aid,
                'title': title_map.get(aid, ''),
                'text': text_clean[:2000],
            })
        except OSError:
            pass
    return index


print('Building table of contents...')
TOC, ARTICLE_MAP = build_toc()
total = len(ARTICLE_MAP)
print(f'Building search index for {total} articles...')
SEARCH_INDEX = build_search_index(ARTICLE_MAP, TOC)
ANN_IDS = set(ANNOTATIONS.keys())
CARD_IDS = set(get_all_card_ids())
print(f'Ready: {total} articles, {len(ANN_IDS)} annotated, {len(CARD_IDS)} with cards')


class Handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path in ('/', '/index.html'):
            self._static_file('index.html', 'text/html; charset=utf-8')
        elif path == '/api/toc':
            summaries = []
            for i, v in enumerate(TOC):
                count = sum(len(s['articles']) for s in v.get('sections', []))
                count += len(v.get('articles', []))
                summaries.append({'vi': i, 'name': v['name'], 'count': count})
            self._json(summaries)
        elif path == '/api/toc/volume':
            qs = parse_qs(parsed.query)
            try:
                vi = int(qs['vi'][0])
            except (KeyError, ValueError, IndexError):
                self.send_error(400, 'Bad Request')
                return
            if 0 <= vi < len(TOC):
                self._json(TOC[vi])
            else:
                self.send_error(404, 'Volume not found')
        elif path == '/api/articles':
            arts = []
            for v in TOC:
                for s in v.get('sections', []):
                    for a in s['articles']:
                        arts.append({'id': a['id'], 'title': a['title']})
                for a in v.get('articles', []):
                    arts.append({'id': a['id'], 'title': a['title']})
            self._json(arts)
        elif path == '/api/article':
            qs = parse_qs(parsed.query)
            try:
                aid = int(qs['id'][0])
            except (KeyError, ValueError, IndexError):
                self.send_error(400, 'Bad Request')
                return
            if aid not in ARTICLE_MAP:
                self.send_error(404, 'Article not found')
                return
            try:
                with open(ARTICLE_MAP[aid], encoding='utf-8') as f:
                    content = f.read()
                self._json({'id': aid, 'content': content})
            except OSError as e:
                self.send_error(500, str(e))
        elif path == '/api/annotations':
            qs = parse_qs(parsed.query)
            try:
                aid = int(qs['id'][0])
            except (KeyError, ValueError, IndexError):
                self.send_error(400, 'Bad Request')
                return
            ann = get_annotation(aid)
            self._json(ann)
        elif path == '/api/annotations/list':
            self._json(sorted(ANNOTATIONS.keys()))
        elif path == '/api/cards':
            qs = parse_qs(parsed.query)
            try:
                aid = int(qs['id'][0])
            except (KeyError, ValueError, IndexError):
                self.send_error(400, 'Bad Request')
                return
            cards = get_cards(aid)
            self._json(cards or [])
        elif path == '/api/cards/list':
            self._json(get_all_card_ids())
        elif path == '/api/search':
            qs = parse_qs(parsed.query)
            q = qs.get('q', [''])[0].strip()
            if not q:
                self._json([])
                return
            results = []
            ql = q.lower()
            for item in SEARCH_INDEX:
                title_match = ql in item['title'].lower()
                text_match = ql in item['text'].lower()
                if title_match or text_match:
                    snippet = ''
                    if text_match:
                        pos = item['text'].lower().find(ql)
                        start = max(0, pos - 40)
                        end = min(len(item['text']), pos + len(q) + 60)
                        snippet = ('…' if start > 0 else '') + item['text'][start:end] + ('…' if end < len(item['text']) else '')
                    results.append({
                        'id': item['id'],
                        'title': item['title'],
                        'snippet': snippet,
                        'titleMatch': title_match,
                    })
                    if len(results) >= 30:
                        break
            results.sort(key=lambda r: (not r['titleMatch'], r['id']))
            self._json(results)
        elif path == '/api/meta':
            self._json({
                'total': total,
                'annIds': sorted(ANN_IDS),
                'cardIds': sorted(CARD_IDS),
            })
        else:
            clean = path.lstrip('/')
            if '..' in clean or clean.startswith('/'):
                self.send_error(403)
                return
            ext = os.path.splitext(clean)[1].lower()
            if ext in STATIC_WHITELIST:
                fpath = os.path.join(STATIC_DIR, clean)
                if os.path.isfile(fpath):
                    ctype = mimetypes.guess_type(fpath)[0] or 'application/octet-stream'
                    self._static_file(clean, ctype, cache=True)
                    return
            self.send_error(404)

    def _static_file(self, relpath, ctype, cache=False):
        fpath = os.path.join(STATIC_DIR, relpath)
        try:
            with open(fpath, 'rb') as f:
                data = f.read()
        except FileNotFoundError:
            self.send_error(404)
            return

        accept_enc = self.headers.get('Accept-Encoding', '')
        use_gzip = 'gzip' in accept_enc and ctype.split(';')[0].strip() in COMPRESSIBLE and len(data) > 512

        if use_gzip:
            data = gzip.compress(data, compresslevel=6)

        self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', len(data))
        if use_gzip:
            self.send_header('Content-Encoding', 'gzip')
        if cache:
            self.send_header('Cache-Control', 'public, max-age=86400')
        else:
            self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        self.wfile.write(data)

    def _json(self, obj, cache_secs=0):
        body = json.dumps(obj, ensure_ascii=False, separators=(',', ':')).encode('utf-8')

        accept_enc = self.headers.get('Accept-Encoding', '')
        use_gzip = 'gzip' in accept_enc and len(body) > 512
        if use_gzip:
            body = gzip.compress(body, compresslevel=6)

        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', len(body))
        if use_gzip:
            self.send_header('Content-Encoding', 'gzip')
        if cache_secs:
            self.send_header('Cache-Control', f'public, max-age={cache_secs}')
        self.end_headers()
        self.wfile.write(body)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    srv = HTTPServer(('0.0.0.0', port), Handler)
    print(f'\n★  读毛选  http://localhost:{port}\n')
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print('Stopped.')
