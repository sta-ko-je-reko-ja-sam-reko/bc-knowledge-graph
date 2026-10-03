"""bckg report: one self-contained HTML page that answers every question without parameters."""
import html
from datetime import datetime, timezone

from .questions import QUESTIONS, overview

ROW_LIMIT = 100

CSS = """
:root { --bg:#f7f7f5; --card:#fff; --text:#1d1d1f; --muted:#62636a; --line:#e3e3e0; --accent:#2856c8;
        --ok:#1f7a45; --ok-bg:#e6f4ec; --warn:#a4400f; --warn-bg:#fbeee6; --info:#3c4a6b; --info-bg:#eaeef7;
        --code:#f0f0ed; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
        --bg:#141416; --card:#1d1d20; --text:#ececef; --muted:#a2a3ab; --line:#2f2f34; --accent:#8aa8ff;
        --ok:#7fd3a0; --ok-bg:#1b3326; --warn:#ffb08a; --warn-bg:#3a2419; --info:#b9c6e6; --info-bg:#232a3a;
        --code:#26262a; } }
* { box-sizing: border-box; }
html { -webkit-text-size-adjust:100%; }
body { margin:0; overflow-wrap:anywhere; background:var(--bg); color:var(--text); font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif; }
main { max-width:1180px; margin:0 auto; padding:32px 16px 64px; }
.totals { display:grid; grid-template-columns:repeat(auto-fit,minmax(min(140px,100%),1fr)); gap:12px; margin:24px 0; }
.total { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:12px 14px; }
.total b { display:block; font-size:22px; }
.total span { color:var(--muted); font-size:13px; }
nav { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:14px 18px; margin-bottom:24px; }
nav ul { margin:0; padding:0; list-style:none; display:grid; grid-template-columns:repeat(auto-fit,minmax(min(300px,100%),1fr)); gap:6px 18px; }
nav a { color:var(--text); text-decoration:none; } nav a:hover { color:var(--accent); }
a { color:var(--accent); }
section { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:20px 22px; margin-bottom:18px; }
section h2 { font-size:19px; margin:0 0 4px; display:flex; gap:10px; align-items:center; flex-wrap:wrap; }
.ask { margin:0 0 4px; font-weight:500; }
.explain { margin:0 0 14px; color:var(--muted); }
.badge { font-size:12px; font-weight:600; padding:2px 9px; border-radius:999px; white-space:nowrap; }
.ok { color:var(--ok); background:var(--ok-bg); } .warn { color:var(--warn); background:var(--warn-bg); }
.info { color:var(--info); background:var(--info-bg); }
.scroll { overflow-x:auto; }
table { border-collapse:collapse; width:100%; font-size:13.5px; }
th, td { text-align:left; vertical-align:top; padding:7px 10px; border-bottom:1px solid var(--line); }
th { color:var(--muted); font-weight:600; font-size:12px; text-transform:uppercase; letter-spacing:.03em; }
td code, .chip { font-family:ui-monospace,"Cascadia Code",Consolas,monospace; font-size:12.5px; }
.chip { display:inline-block; background:var(--code); border-radius:5px; padding:0 6px; margin:1px 3px 1px 0; }
.empty { color:var(--ok); margin:4px 0 0; }
details summary { cursor:pointer; color:var(--accent); margin-top:10px; }
.hero { padding:8px 0 4px; }
.eyebrow { text-transform:uppercase; letter-spacing:.08em; font-size:12px; font-weight:600; color:var(--accent); margin:0 0 6px; }
.hero h1 { font-size:34px; line-height:1.15; margin:0 0 14px; letter-spacing:-0.02em; }
.lead { font-size:17px; line-height:1.6; max-width:820px; margin:0 0 18px; }
.intro-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(min(260px,100%),1fr)); gap:14px; margin:6px 0 18px; }
.intro-grid > div { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:16px 18px; }
.intro-grid h3 { margin:0 0 6px; font-size:15px; }
.intro-grid p { margin:0; color:var(--muted); font-size:14px; }
.meta { color:var(--muted); font-size:13px; margin:0; }
.legend h2, nav h2 { font-size:13px; text-transform:uppercase; letter-spacing:.05em; color:var(--muted); margin:0 0 10px; }
.legend ul { margin:0; padding:0; list-style:none; display:grid; gap:8px; }
.legend li { display:flex; gap:10px; align-items:baseline; flex-wrap:wrap; }
.products { display:grid; grid-template-columns:repeat(auto-fit,minmax(min(330px,100%),1fr)); gap:14px; }
.product { border:1px solid var(--line); border-radius:10px; padding:16px; }
.product h3 { margin:0 0 6px; font-size:16px; }
.desc { margin:0 0 8px; color:var(--muted); font-size:14px; }
.repos { margin:0 0 10px; display:flex; gap:6px 12px; flex-wrap:wrap; font-size:13px; }
.apps { list-style:none; margin:0; padding:0; }
.apps li { display:flex; justify-content:space-between; gap:8px; flex-wrap:wrap; padding:6px 0; border-top:1px solid var(--line); font-size:13.5px; }
.apps .facts { display:flex; gap:10px; color:var(--muted); flex-wrap:wrap; align-items:baseline; }
.tag { font-size:11px; color:var(--muted); border:1px solid var(--line); border-radius:4px; padding:0 4px; }
.contracts { margin:10px 0 0; font-size:13px; color:var(--muted); }
section.legend, nav { margin-bottom:18px; }
@media (max-width: 600px) { .hero h1 { font-size:27px; } .lead { font-size:16px; } .products { grid-template-columns:1fr; } }
footer { color:var(--muted); font-size:13px; text-align:center; margin-top:32px; }
footer a { color:var(--muted); }
"""


class Link(str):
    """A table value rendered as a link."""

    def __new__(cls, text, href):
        value = super().__new__(cls, text)
        value.href = href
        return value


def esc(value):
    return html.escape('' if value is None else str(value))


def cell(value):
    if value is None:
        return ''
    if isinstance(value, Link):
        return '<a href="%s">%s</a>' % (esc(value.href), esc(value))
    if isinstance(value, bool):
        return 'yes' if value else 'no'
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, dict) and 'owner' in item:
                parts.append('<span class="chip">%s</span> %s' % (esc(item['owner']), esc(', '.join(item['how']))))
            elif isinstance(item, dict) and 'object' in item:
                parts.append('<span class="chip">%s</span> %s' % (esc(item['object']), esc(', '.join(item.get('via') or []))))
            else:
                parts.append('<span class="chip">%s</span>' % esc(item))
        return '<br>'.join(parts) if any(isinstance(i, dict) for i in value) else ' '.join(parts)
    return esc(value)


def table(columns, rows, labels=None):
    labels = labels or {}
    head = ''.join('<th>%s</th>' % esc(labels.get(c, c)) for c in columns)

    def body(chunk):
        return ''.join('<tr>%s</tr>' % ''.join('<td>%s</td>' % cell(r.get(c)) for c in columns) for r in chunk)
    out = '<div class="scroll"><table><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>' % (
        head, body(rows[:ROW_LIMIT]))
    if len(rows) > ROW_LIMIT:
        out += ('<details><summary>Show the other %d rows</summary><div class="scroll"><table><thead><tr>%s</tr>'
                '</thead><tbody>%s</tbody></table></div></details>' % (len(rows) - ROW_LIMIT, head, body(rows[ROW_LIMIT:])))
    return out


def anchor(question_id):
    return 'q-' + question_id.replace('_', '-')


REPO_URL = 'https://github.com/sta-ko-je-reko-ja-sam-reko/bc-knowledge-graph'

DEFAULT_INTRO = """<p class="lead">This page is built from the AL source of the apps below: their objects, the standard
objects and events they touch, their features and tests, and the API contracts around them. It answers, for all of
the apps at once, the questions that are hard to answer one repository at a time.</p>"""

LEGEND = """<section class="legend" aria-label="How to read this page">
<h2>How to read this page</h2>
<ul>
<li><span class="badge ok">✓ none found</span> A check passed: nothing that would stop the apps from working together.</li>
<li><span class="badge warn">3 found</span> A check found something to fix or review; the rows below say what.</li>
<li><span class="badge info">12</span> Not a problem in itself: places where products meet, worth testing together.</li>
</ul>
</section>"""


def plural(count, noun):
    return '%s %s%s' % (f'{count:,}', noun, '' if count == 1 else 's')


def product_cards(info):
    cards = []
    for product in info['products']:
        repos = ' '.join('<a class="repo" href="https://github.com/%s">%s</a>' % (esc(r['github']), esc(r['repo']))
                         if r.get('github') else '<span class="repo">%s</span>' % esc(r['repo'])
                         for r in product['repos'])
        apps = ''.join(
            '<li><span class="app">%s%s</span><span class="facts">%s<span>%s</span><span>%s</span>'
            '<span>%s</span></span></li>' % (
                esc(a['app']), ' <span class="tag">tests</span>' if a['isTest'] else '',
                ''.join('<span class="chip">%s</span>' % esc(r) for r in a.get('idRanges') or []),
                plural(a['objects'], 'object'), plural(a['features'], 'feature'), plural(a['tests'], 'test'))
            for a in product['apps'])
        contracts = ''.join('<span class="chip">%s</span>' % esc(c) for c in product['contracts'])
        cards.append('<article class="product"><h3>%s</h3>%s<p class="repos">%s</p><ul class="apps">%s</ul>%s</article>' % (
            esc(product['product']),
            '<p class="desc">%s</p>' % esc(product['description']) if product.get('description') else '',
            repos, apps, '<p class="contracts">Contracts: %s</p>' % contracts if contracts else ''))
    return ('<section id="products"><h2>The products</h2><p class="explain">What the graph was built from, with the '
            'object ID range each app owns.</p><div class="products">%s</div></section>' % ''.join(cards))


def render(view, title='Business Central knowledge graph', group_by='product', source=None, graph_url=None,
           intro=None):
    """The whole page. `intro` is an HTML fragment shown under the title instead of the default lead."""
    info = overview(view)
    owner_label = {'owners': 'products' if group_by == 'product' else 'apps',
                   'touches': 'by ' + ('product' if group_by == 'product' else 'app')}
    sections = [product_cards(info)]
    nav = ['<li><a href="#products">The products</a></li>']

    has_contracts = info['totals']['contracts'] > 0
    for q in QUESTIONS:
        required = [p for p in q.params if p != 'group_by']
        if required or (q.id.startswith('contract') and not has_contracts):
            continue
        rows = q.run(view, group_by=group_by) if 'group_by' in q.params else q.run(view)
        if q.kind == 'check':
            badge = ('<span class="badge ok">✓ none found</span>' if not rows else
                     '<span class="badge warn">%d found</span>' % len(rows))
        else:
            badge = '<span class="badge info">%d</span>' % len(rows)
        body = table(q.columns, rows, owner_label) if rows else '<p class="empty">Nothing found.</p>'
        sections.append('<section id="%s"><h2>%s %s</h2><p class="ask">%s</p><p class="explain">%s</p>%s</section>' % (
            anchor(q.id), esc(q.title), badge, esc(q.ask), esc(q.explain), body))
        nav.append('<li><a href="#%s">%s</a> %s</li>' % (anchor(q.id), esc(q.title), badge))

    asked = [q for q in QUESTIONS if [p for p in q.params if p != 'group_by']]
    sections.append('<section id="more"><h2>Questions with a parameter</h2><p class="explain">These need an input, so '
                    'they are not on this page. Ask them with <code>bckg ask</code> or through the MCP server.</p>%s'
                    '</section>' % table(['question', 'ask', 'parameter'],
                                         [{'question': q.id, 'ask': q.ask,
                                           'parameter': ', '.join('%s: %s' % kv for kv in q.params.items())}
                                          for q in asked]))
    nav.append('<li><a href="#more">Questions with a parameter</a></li>')

    totals = info['totals']
    cards = ''.join('<div class="total"><b>%s</b><span>%s</span></div>' % (f'{v:,}', esc(k)) for k, v in (
        ('products', len(info['products'])), ('apps', totals['apps']), ('own objects', totals['objects']),
        ('standard objects touched', totals['standardObjectsTouched']), ('features', totals['features']),
        ('test procedures', totals['testProcedures'])))
    stamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    meta = 'Updated %s%s. Overlap is counted between %ss.' % (
        stamp, (' from ' + esc(source)) if source else '', group_by)
    if graph_url:
        meta += (' <a href="%s">Download the graph</a> (JSON, for <code>bckg ask</code> and <code>bckg mcp</code>).'
                 % esc(graph_url))
    return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%s</title>
<meta name="description" content="Business Central apps mapped from their AL source: install-together checks, shared standard objects and events, test coverage and API contracts.">
<style>%s</style>
</head>
<body>
<main>
<header class="hero">
<p class="eyebrow">Business Central knowledge graph</p>
<h1>%s</h1>
%s
<p class="meta">%s</p>
</header>
<div class="totals">%s</div>
%s
<nav aria-label="Contents"><h2>On this page</h2><ul>%s</ul></nav>
%s
<footer>Made with <a href="%s">bc-knowledge-graph</a>, open source (MIT), from AL source declarations;
nothing was compiled or run.</footer>
</main>
</body>
</html>
""" % (esc(title), CSS, esc(title), intro or DEFAULT_INTRO, meta, cards, LEGEND, ''.join(nav), '\n'.join(sections),
       REPO_URL)
