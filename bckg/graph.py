"""In-memory property graph that the extractors fill and the loader writes to Neo4j."""
import json


class Graph:
    def __init__(self):
        self.nodes = {}  # (label, key) -> properties
        self.rels = {}  # (type, (label, key), (label, key)) -> properties

    def node(self, label, key, **props):
        ref = (label, key)
        properties = self.nodes.setdefault(ref, {'key': key})
        properties.update({name: value for name, value in props.items() if value is not None})
        return ref

    def rel(self, rel_type, start, end, **props):
        """Add or update a relationship. `via` (how the link was found) accumulates into a sorted list."""
        existing = self.rels.setdefault((rel_type, start, end), {})
        via = props.pop('via', None)
        if via:
            existing['via'] = sorted(set(existing.get('via', [])) | {via})
        existing.update({name: value for name, value in props.items() if value is not None})

    def has(self, ref):
        return ref in self.nodes

    def outgoing(self, start, rel_type=None):
        return [end for (kind, a, end) in self.rels if a == start and (rel_type is None or kind == rel_type)]

    def to_json(self):
        return {
            'nodes': [{'label': label, **props} for (label, _), props in sorted(self.nodes.items())],
            'rels': [{'type': kind, 'start': list(a), 'end': list(b), 'props': props}
                     for (kind, a, b), props in sorted(self.rels.items())],
        }

    @classmethod
    def from_json(cls, data):
        graph = cls()
        for node in data['nodes']:
            props = dict(node)
            graph.node(props.pop('label'), props.pop('key'), **props)
        for rel in data['rels']:
            graph.rels[(rel['type'], tuple(rel['start']), tuple(rel['end']))] = dict(rel['props'])
        return graph

    def save(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_json(), indent=1, ensure_ascii=False), encoding='utf-8')

    @classmethod
    def load(cls, path):
        return cls.from_json(json.loads(path.read_text(encoding='utf-8')))
