"""Command line: extract the graph, answer questions, write the report, serve MCP, load into Neo4j."""
import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

from .extract import extract
from .graph import Graph


def read_env(path=Path('.env')):
    """Minimal .env reader so the CLI and docker compose share one credentials file."""
    if path.exists():
        for line in path.read_text(encoding='utf-8').splitlines():
            name, sep, value = line.partition('=')
            if sep and not line.lstrip().startswith('#'):
                os.environ.setdefault(name.strip(), value.strip())


def print_stats(graph):
    for label, count in sorted(Counter(label for label, _ in graph.nodes).items()):
        print('  %-14s %6d' % (label, count))
    print('  ' + '-' * 21)
    for rel_type, count in sorted(Counter(kind for kind, _, _ in graph.rels).items()):
        print('  %-14s %6d' % (rel_type, count))


def main(argv=None):
    read_env()
    parser = argparse.ArgumentParser(prog='bckg', description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    run = commands.add_parser('extract', help='read the repositories and write out/graph.json')
    run.add_argument('--config', default='products.yaml')
    run.add_argument('--out', default='out/graph.json')
    load_cmd = commands.add_parser('load', help='replace the Neo4j database content with out/graph.json')
    load_cmd.add_argument('--graph', default='out/graph.json')
    query_cmd = commands.add_parser('query', help='run a saved query, for example queries/id-collisions.cypher')
    query_cmd.add_argument('file')
    query_cmd.add_argument('--param', action='append', default=[], metavar='NAME=VALUE')
    for command in (load_cmd, query_cmd):
        command.add_argument('--uri', default=os.environ.get('NEO4J_URI', 'bolt://localhost:7687'))
        command.add_argument('--user', default=os.environ.get('NEO4J_USER', 'neo4j'))
        command.add_argument('--database', default=os.environ.get('NEO4J_DATABASE'))
    stats = commands.add_parser('stats', help='count nodes and relationships in out/graph.json')
    stats.add_argument('--graph', default='out/graph.json')
    ask = commands.add_parser('ask', help='answer one question from out/graph.json (no Neo4j needed)')
    ask.add_argument('question', nargs='?', help='question id; leave out to list them')
    ask.add_argument('--param', action='append', default=[], metavar='NAME=VALUE')
    ask.add_argument('--graph', default='out/graph.json')
    report = commands.add_parser('report', help='write one HTML page that answers every question')
    report.add_argument('--graph', default='out/graph.json')
    report.add_argument('--out', default='out/report.html')
    report.add_argument('--title', default='Business Central knowledge graph')
    report.add_argument('--group-by', choices=['product', 'app'], default='product')
    report.add_argument('--source', help='where the graph came from, shown under the title')
    report.add_argument('--graph-url', help='link to a downloadable copy of the graph')
    mcp = commands.add_parser('mcp', help='serve the graph to Claude and other MCP clients')
    mcp.add_argument('--graph', default='out/graph.json')
    mcp.add_argument('--http', action='store_true', help='streamable HTTP on --host/--port instead of stdio')
    mcp.add_argument('--host', default='127.0.0.1')
    mcp.add_argument('--port', type=int, default=8765)
    args = parser.parse_args(argv)

    if args.command == 'extract':
        graph, warnings = extract(args.config)
        graph.save(Path(args.out))
        print('wrote %s: %d nodes, %d relationships' % (args.out, len(graph.nodes), len(graph.rels)))
        print_stats(graph)
        for warning in warnings:
            print('warning:', warning, file=sys.stderr)
    elif args.command in ('load', 'query'):
        from .load import load, query
        password = os.environ.get('NEO4J_PASSWORD')
        if not password:
            parser.error('set NEO4J_PASSWORD (for example in .env)')
        if args.command == 'load':
            nodes, rels = load(Graph.load(Path(args.graph)), args.uri, args.user, password, args.database)
            print('loaded %d nodes and %d relationships into %s' % (nodes, rels, args.uri))
        else:
            params = dict(param.split('=', 1) for param in args.param)
            keys, rows = query(Path(args.file), args.uri, args.user, password, args.database, params)
            print('\t'.join(keys))
            for row in rows:
                print('\t'.join(str(value) for value in row))
            print('(%d rows)' % len(rows), file=sys.stderr)
    elif args.command == 'ask':
        from .questions import QUESTIONS, View, answer
        if not args.question:
            for question in QUESTIONS:
                params = ' '.join('--param %s=...' % name for name in question.params)
                print('%-26s %s %s' % (question.id, question.ask, params))
            return 0
        params = dict(param.split('=', 1) for param in args.param)
        rows = answer(View(Graph.load(Path(args.graph))), args.question, **params)
        print(json.dumps(rows, indent=1, ensure_ascii=False))
        print('(%d rows)' % len(rows), file=sys.stderr)
    elif args.command == 'report':
        from .questions import View
        from .report import render
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render(View(Graph.load(Path(args.graph))), args.title, args.group_by,
                                    args.source, args.graph_url), encoding='utf-8')
        print('wrote', out)
    elif args.command == 'mcp':
        from .mcp_server import serve
        if args.http and args.host not in ('127.0.0.1', 'localhost'):
            print('warning: the MCP server has no authentication; do not expose it publicly', file=sys.stderr)
        serve(args.graph, 'http' if args.http else 'stdio', args.host, args.port)
    else:
        print_stats(Graph.load(Path(args.graph)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
