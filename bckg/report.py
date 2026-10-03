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
body { margin:0; background:var(--bg); color:var(--text); font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif; }
main { max-width:1180px; margin:0 auto; padding:32px 16px 64px; }
header h1 { font-size:28px; margin:0 0 4px; letter-spacing:-0.01em; }
header p { margin:0; color:var(--muted); }
.totals { display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:12px; margin:24px 0; }
.total { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:12px 14px; }
.total b { display:block; font-size:22px; }
.total span { color:var(--muted); font-size:13px; }
nav { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:14px 18px; margin-bottom:24px; }
nav ul { margin:0; padding:0; list-style:none; display:grid; grid-template-columns:repeat(auto-fit,minmax(300px,1fr)); gap:6px 18px; }
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


def render(view, title='Business Central knowledge graph', group_by='product', source=None, graph_url=None):
    info = overview(view)
    owner_label = {'owners': 'products' if group_by == 'product' else 'apps',
                   'touches': 'by ' + ('product' if group_by == 'product' else 'app')}
    sections, nav = [], []

    apps = [dict(a, product=p['product']) for p in info['products'] for a in p['apps']]
    for app in apps:
        if app.get('github'):
            app['repo'] = Link(app['repo'], 'https://github.com/%s' % app['github'])
    sections.append('<section id="apps"><h2>Products and apps</h2><p class="explain">What the graph was built from.'
                    '</p>%s</section>' % table(['product', 'app', 'repo', 'version', 'idRanges', 'objects', 'features',
                                                'tests'], apps, {'idRanges': 'ID ranges'}))
    nav.append('<li><a href="#apps">Products and apps</a></li>')

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

    totals = info['totals']
    cards = ''.join('<div class="total"><b>%s</b><span>%s</span></div>' % (f'{v:,}', esc(k)) for k, v in (
        ('apps', totals['apps']), ('own objects', totals['objects']),
        ('standard objects touched', totals['standardObjectsTouched']), ('features', totals['features']),
        ('test procedures', totals['testProcedures']), ('contracts', totals['contracts'])))
    stamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    subtitle = 'Generated %s%s. Overlap is counted between %ss.' % (
        stamp, (' from ' + esc(source)) if source else '', group_by)
    if graph_url:
        subtitle += ' <a href="%s">Download the graph</a> (JSON, for <code>bckg ask</code> and <code>bckg mcp</code>).' % esc(graph_url)
    return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%s</title>
<style>%s</style>
</head>
<body>
<main>
<header><h1>%s</h1><p>%s</p></header>
<div class="totals">%s</div>
<nav><ul>%s</ul></nav>
%s
<footer>Built with <a href="https://github.com/sta-ko-je-reko-ja-sam-reko/bc-knowledge-graph">bc-knowledge-graph</a>
from AL source declarations; nothing was compiled or run.</footer>
</main>
</body>
</html>
""" % (esc(title), CSS, esc(title), subtitle, cards, ''.join(nav), '\n'.join(sections))
