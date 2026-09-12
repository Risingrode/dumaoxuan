#!/usr/bin/env python3
"""读毛选 — 毛泽东选集在线阅读服务"""
import os
import json
import re
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from annotations import get_annotation, ANNOTATIONS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONTENT_DIR = os.path.join(BASE_DIR, 'MaoZeDongAnthology')

NUM_PREFIX = re.compile(r'^\d+[\s\-]+')


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


print('Building table of contents...')
TOC, ARTICLE_MAP = build_toc()
total = len(ARTICLE_MAP)
print(f'Ready: {total} articles across {len(TOC)} volumes')


class Handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path in ('/', '/index.html'):
            self._file(os.path.join(BASE_DIR, 'index.html'), 'text/html; charset=utf-8')
        elif path == '/api/toc':
            self._json(TOC)
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
            if ann is None:
                self._json(None)
            else:
                self._json(ann)
        elif path == '/api/annotations/list':
            # Return list of article IDs that have annotations
            self._json(list(ANNOTATIONS.keys()))
        else:
            self.send_error(404)

    def _file(self, path, ctype):
        try:
            with open(path, 'rb') as f:
                data = f.read()
        except FileNotFoundError:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', len(data))
        self.end_headers()
        self.wfile.write(data)

    def _json(self, obj):
        body = json.dumps(obj, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)


if __name__ == '__main__':
    port = 8080
    srv = HTTPServer(('0.0.0.0', port), Handler)
    print(f'\n★  读毛选  http://localhost:{port}\n')
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print('Stopped.')
