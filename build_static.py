#!/usr/bin/env python3
"""把 server.py 的全部 /api 接口预先生成为静态 JSON，输出到 _site/，用于 GitHub Pages 等静态托管。

用法：python build_static.py   （本地预览：cd _site && python -m http.server）
index.html 本身不改动；构建时注入一段 fetch 转接脚本，把 /api/... 请求映射到静态文件，搜索在浏览器端完成。
"""
import json
import os
import re
import shutil

import server  # 导入即构建目录与搜索索引（server.py 的 main 有 __name__ 守卫，不会启动服务）
from annotations import get_annotation, get_cards

BASE = server.BASE_DIR
OUT = os.path.join(BASE, '_site')


def dump(rel, obj):
    path = os.path.join(OUT, 'api', rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, separators=(',', ':'))


# 浏览器端转接：与 server.py 中各接口的行为保持一致（搜索逻辑逐行对应 /api/search）
SHIM = r"""<script>
(function () {
  var BASE = new URL('.', location.href).href, origFetch = window.fetch.bind(window), idx = null;
  function json(o) { return new Response(JSON.stringify(o), { headers: { 'Content-Type': 'application/json; charset=utf-8' } }); }
  function file(rel) { return origFetch(BASE + 'api/' + rel); }
  async function search(q) {
    q = (q || '').trim(); if (!q) return json([]);
    if (!idx) idx = await (await file('search.json')).json();
    var ql = q.toLowerCase(), results = [];
    for (var i = 0; i < idx.length; i++) {
      var it = idx[i], tl = it.title.toLowerCase(), xl = it.text.toLowerCase();
      var tm = tl.indexOf(ql) >= 0, xm = xl.indexOf(ql) >= 0;
      if (!tm && !xm) continue;
      var snippet = '';
      if (xm) {
        var pos = xl.indexOf(ql), s = Math.max(0, pos - 40), e = Math.min(it.text.length, pos + q.length + 60);
        snippet = (s > 0 ? '…' : '') + it.text.slice(s, e) + (e < it.text.length ? '…' : '');
      }
      results.push({ id: it.id, title: it.title, snippet: snippet, titleMatch: tm });
      if (results.length >= 30) break;
    }
    results.sort(function (a, b) { return (a.titleMatch === b.titleMatch) ? a.id - b.id : (a.titleMatch ? -1 : 1); });
    return json(results);
  }
  window.fetch = function (u, o) {
    if (typeof u === 'string' && u.indexOf('/api/') === 0) {
      var url = new URL(u, location.origin), p = url.pathname, id = url.searchParams.get('id'), vi = url.searchParams.get('vi');
      switch (p) {
        case '/api/search': return search(url.searchParams.get('q'));
        case '/api/toc': case '/api/articles': case '/api/meta': return file(p.slice(5) + '.json');
        case '/api/toc/volume': return file('toc/volume/' + parseInt(vi, 10) + '.json');
        case '/api/annotations/list': case '/api/cards/list': return file(p.slice(5) + '.json');
        case '/api/article': return file('article/' + parseInt(id, 10) + '.json');
        case '/api/annotations': return file('annotations/' + parseInt(id, 10) + '.json');
        case '/api/cards': return file('cards/' + parseInt(id, 10) + '.json');
      }
    }
    return origFetch(u, o);
  };
})();
</script>
"""


def patch_html(html):
    # 站点部署在子路径（如 /dumaoxuan/）下：根路径引用改为相对路径
    html = html.replace('href="/favicon.svg"', 'href="favicon.svg"').replace('href="/manifest.json"', 'href="manifest.json"')
    html = html.replace("history.replaceState(null, '', '/')", "history.replaceState(null, '', location.pathname)")
    html = html.replace("location.origin + '/?id='", "location.origin + location.pathname + '?id='")
    return re.sub(r'(<head[^>]*>)', lambda m: m.group(1) + '\n' + SHIM, html, count=1)


def main():
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT)
    toc, amap = server.TOC, server.ARTICLE_MAP

    summaries = []
    for i, v in enumerate(toc):
        count = sum(len(s['articles']) for s in v.get('sections', [])) + len(v.get('articles', []))
        summaries.append({'vi': i, 'name': v['name'], 'count': count})
        dump(f'toc/volume/{i}.json', v)
    dump('toc.json', summaries)

    arts = []
    for v in toc:
        for s in v.get('sections', []):
            arts += [{'id': a['id'], 'title': a['title']} for a in s['articles']]
        arts += [{'id': a['id'], 'title': a['title']} for a in v.get('articles', [])]
    dump('articles.json', arts)

    for aid, path in amap.items():
        with open(path, encoding='utf-8') as f:
            dump(f'article/{aid}.json', {'id': aid, 'content': f.read()})
        dump(f'annotations/{aid}.json', get_annotation(aid))
        dump(f'cards/{aid}.json', get_cards(aid) or [])

    dump('annotations/list.json', sorted(server.ANNOTATIONS.keys()))
    dump('cards/list.json', server.get_all_card_ids())
    dump('meta.json', {'total': server.total, 'annIds': sorted(server.ANN_IDS), 'cardIds': sorted(server.CARD_IDS)})
    dump('search.json', server.SEARCH_INDEX)

    for name in ('index.html', 'artifact.html'):
        with open(os.path.join(BASE, name), encoding='utf-8') as f:
            html = f.read()
        with open(os.path.join(OUT, name), 'w', encoding='utf-8') as f:
            f.write(patch_html(html))

    shutil.copy(os.path.join(BASE, 'favicon.svg'), OUT)
    with open(os.path.join(BASE, 'manifest.json'), encoding='utf-8') as f:
        mani = json.load(f)
    mani['start_url'] = './'
    for ic in mani.get('icons', []):
        ic['src'] = ic['src'].lstrip('/')
    with open(os.path.join(OUT, 'manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(mani, f, ensure_ascii=False, indent=2)
    open(os.path.join(OUT, '.nojekyll'), 'w').close()
    print(f'Static site written to {OUT}: {len(amap)} articles')


if __name__ == '__main__':
    main()
