"""Command line: extract the graph to JSON, load it into Neo4j, print statistics."""
import argparse
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
    else:
        print_stats(Graph.load(Path(args.graph)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
