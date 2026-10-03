"""The questions the graph answers, computed in Python from out/graph.json (no Neo4j needed).

Each question has a saved Cypher twin in queries/ that returns the same rows; tests/test_parity.py checks
that against a real Neo4j. The report (bckg report) and the MCP server (bckg mcp) are both built from QUESTIONS.
"""
from collections import defaultdict
from dataclasses import dataclass, field


class View:
    """Indexes over a Graph: adjacency in both directions and the owner (product, app) of every object."""

    def __init__(self, graph):
        self.graph = graph
        self.nodes = graph.nodes
        self.out = defaultdict(lambda: defaultdict(list))
        self.inc = defaultdict(lambda: defaultdict(list))
        for (rel_type, start, end), props in graph.rels.items():
            self.out[start][rel_type].append((end, props))
            self.inc[end][rel_type].append((start, props))
        self.app_of = {}
        self.product_of_app = {}
        for product in self.label('Product'):
            for repo, _ in self.out[product]['HAS_REPO']:
                for app, _ in self.out[repo]['CONTAINS']:
                    self.product_of_app[app] = self.nodes[product]['name']
                    for obj, _ in self.out[app]['CONTAINS']:
                        self.app_of[obj] = app

    def label(self, label):
        return [ref for ref in self.nodes if ref[0] == label]

    def node(self, ref):
        return self.nodes[ref]

    def targets(self, ref, rel_type):
        return [end for end, _ in self.out[ref][rel_type]]

    def sources(self, ref, rel_type):
        return [start for start, _ in self.inc[ref][rel_type]]

    def owner(self, obj, group_by):
        app = self.app_of.get(obj)
        if app is None:
            return None
        return self.product_of_app[app] if group_by == 'product' else self.nodes[app]['name']

    def is_test_app(self, app):
        return bool(self.nodes[app].get('isTest'))


@dataclass
class Question:
    id: str
    title: str
    ask: str  # the question in plain language
    explain: str  # why it matters / how to read the result
    columns: list
    run: callable
    kind: str = 'insight'  # 'check': an empty answer is the good outcome
    params: dict = field(default_factory=dict)  # name -> description
    cypher: str = None  # file in queries/ that returns the same rows


def by(rows, *keys, reverse_first=False):
    return sorted(rows, key=lambda r: tuple((-r[k] if reverse_first and i == 0 else r[k]) if r[k] is not None else ''
                                            for i, k in enumerate(keys)))


# ------------------------------------------------------------------------------------------------ checks
def id_collisions(view):
    groups = defaultdict(lambda: (set(), []))
    for app in view.label('App'):
        if view.node(app).get('origin') != 'own':
            continue
        for obj in view.targets(app, 'CONTAINS'):
            node = view.node(obj)
            if node.get('id') is not None:
                apps, objects = groups[(node['type'], node['id'])]
                apps.add(view.node(app)['name'])
                objects.append(node['name'])
    rows = [{'type': t, 'id': i, 'apps': sorted(a), 'objects': sorted(o)}
            for (t, i), (a, o) in groups.items() if len(a) > 1]
    return by(rows, 'type', 'id')


def field_collisions(view):
    by_id = defaultdict(lambda: (set(), set()))
    by_name = defaultdict(set)
    for app in view.label('App'):
        for obj in view.targets(app, 'CONTAINS'):
            for fld in view.targets(obj, 'ADDS_FIELD'):
                for table in view.targets(fld, 'OF_TABLE'):
                    node = view.node(fld)
                    apps, names = by_id[(view.node(table)['name'], node.get('id'))]
                    apps.add(view.node(app)['name'])
                    names.add(node['name'])
                    by_name[(view.node(table)['name'], node['name'])].add(view.node(app)['name'])
    rows = [{'table': t, 'clash': None if i is None else 'field ID %s' % i, 'apps': sorted(a), 'fields': sorted(n)}
            for (t, i), (a, n) in by_id.items() if len(a) > 1]
    rows += [{'table': t, 'clash': 'field name', 'apps': sorted(a), 'fields': [n]}
             for (t, n), a in by_name.items() if len(a) > 1]
    return by(rows, 'table', 'clash')


# ------------------------------------------------------------------------------------------------ overlap
def shared_standard_objects(view, group_by='product'):
    touches = defaultdict(lambda: defaultdict(set))
    for obj, app in view.app_of.items():
        if view.is_test_app(app):
            continue
        owner = view.owner(obj, group_by)
        for rel_type in ('EXTENDS', 'USES', 'SUBSCRIBES_TO'):
            for target in view.targets(obj, rel_type):
                if target[0] == 'Event':
                    target = next(iter(view.targets(target, 'PUBLISHED_BY')), None)
                if target and view.node(target).get('origin') == 'standard':
                    touches[target][owner].add(rel_type)
    rows = [{'type': view.node(t)['type'], 'object': view.node(t)['name'], 'owners': len(o),
             'touches': [{'owner': name, 'how': sorted(how)} for name, how in sorted(o.items())]}
            for t, o in touches.items() if len(o) > 1]
    return by(rows, 'owners', 'object', reverse_first=True)


def shared_events(view, group_by='product'):
    events = defaultdict(lambda: (set(), []))
    for obj in view.app_of:
        for event, props in view.out[obj]['SUBSCRIBES_TO']:
            owners, subscribers = events[event]
            owners.add(view.owner(obj, group_by))
            subscribers.append('%s.%s' % (view.node(obj)['name'], props.get('procedure')))
    rows = [{'publisher': view.node(e).get('object'), 'event': view.node(e)['name'], 'field': view.node(e).get('element'),
             'owners': sorted(o), 'subscribers': sorted(s)} for e, (o, s) in events.items() if len(o) > 1]
    rows = by(rows, 'publisher', 'event')
    return sorted(rows, key=lambda r: -len(r['owners']))


def product_overlap(view, group_by='product'):
    touched = defaultdict(set)  # owner -> standard objects it extends, uses or subscribes to (test apps left out)
    for obj, app in view.app_of.items():
        if view.is_test_app(app):
            continue
        for rel_type in ('EXTENDS', 'USES', 'SUBSCRIBES_TO'):
            for target in view.targets(obj, rel_type):
                if target[0] == 'Event':
                    target = next(iter(view.targets(target, 'PUBLISHED_BY')), None)
                if target and view.node(target).get('origin') == 'standard':
                    touched[view.owner(obj, group_by)].add(target)
    owners = sorted(touched)
    rows = []
    for i, first in enumerate(owners):
        for second in owners[i + 1:]:
            shared = touched[first] & touched[second]
            if shared:
                rows.append({'first': first, 'second': second, 'shared': len(shared),
                             'objects': sorted('%s %s' % (view.node(t)['type'], view.node(t)['name']) for t in shared)})
    return by(rows, 'shared', 'first', 'second', reverse_first=True)


# ------------------------------------------------------------------------------------------------ features
def features_without_tests(view):
    rows = []
    for app in view.label('App'):
        for feature in view.targets(app, 'HAS_FEATURE'):
            if view.sources(feature, 'VERIFIES'):
                continue
            objects = view.targets(feature, 'IMPLEMENTED_BY')
            if any(view.node(user).get('isTest') for obj in objects for user in view.sources(obj, 'USES')):
                continue
            node = view.node(feature)
            rows.append({'app': view.node(app)['name'], 'feature': node['code'], 'name': node['name'],
                         'linkedObjects': len(set(objects))})
    return by(rows, 'app', 'feature')


def feature_trace(view, feature):
    rows = []
    for app in view.label('App'):
        for ref in view.targets(app, 'HAS_FEATURE'):
            node = view.node(ref)
            if node['code'] != feature:
                continue
            objects, touches = [], set()
            for obj, props in view.out[ref]['IMPLEMENTED_BY']:
                objects.append({'object': '%s %s' % (view.node(obj)['type'], view.node(obj)['name']),
                                'via': props.get('via')})
                for rel_type in ('EXTENDS', 'SUBSCRIBES_TO'):
                    for target in view.targets(obj, rel_type):
                        t = view.node(target)
                        touches.add('%s::%s' % (t['object'], t['name']) if t.get('object') is not None
                                    else '%s %s' % (t.get('type'), t['name']))
            tests = sorted({'%s.%s' % (view.node(t)['codeunit'], view.node(t)['name'])
                            for t in view.sources(ref, 'VERIFIES')})
            rows.append({'app': view.node(app)['name'], 'name': node['name'], 'docs': node.get('docs'),
                         'objects': sorted(objects, key=lambda o: o['object']), 'tests': tests,
                         'touches': sorted(touches)})
    return by(rows, 'app')


# ------------------------------------------------------------------------------------------------ contracts
def contract_coverage(view):
    rows = []
    for contract in view.label('Contract'):
        for item in view.targets(contract, 'DEFINES'):
            node = view.node(item)
            if item[0] == 'Operation' and not view.sources(item, 'SERVES'):
                rows.append({'contract': contract[1], 'kind': 'operation', 'name': node['name'],
                             'detail': '%s %s' % (node['method'], node['path'])})
            elif item[0] == 'Channel' and not view.sources(item, 'EMITS'):
                rows.append({'contract': contract[1], 'kind': 'channel', 'name': node['name'], 'detail': ''})
    return by(rows, 'contract', 'kind', 'name')


def contract_impact(view, property):
    rows = []
    for prop in view.label('Property'):
        node = view.node(prop)
        if '%s.%s' % (node['schema'], node['name']) != property:
            continue
        schemas = set(view.sources(prop, 'HAS_PROPERTY'))
        frontier = set(schemas)
        for _ in range(10):  # walk up: schema <- HAS_PROPERTY - property <- REFERENCES - ... (at most 10 hops)
            parents = set()
            for ref in frontier:
                parents.update(view.sources(ref, 'REFERENCES' if ref[0] == 'Schema' else 'HAS_PROPERTY'))
            parents -= schemas
            schemas |= {p for p in parents if p[0] == 'Schema'}
            frontier = parents
        operations = sorted({view.node(op)['name'] for s in schemas if s[0] == 'Schema'
                             for op in view.sources(s, 'USES_SCHEMA') if op[0] == 'Operation'})
        op_refs = [op for s in schemas for op in view.sources(s, 'USES_SCHEMA') if op[0] == 'Operation']
        mentions = sorted({'%s: %s' % (view.node(repo)['name'], props.get('file'))
                           for op in op_refs for repo, props in view.inc[op]['MENTIONS']})
        combos = []
        for api in view.targets(prop, 'MAPS_TO'):
            owners = view.sources(api, 'EXPOSES') or [None]
            fields = view.targets(api, 'READS') or [None]
            combos += [(o, api, f) for o in owners for f in fields]
        for owner, api, fld in combos or [(None, None, None)]:
            rows.append({'contract': node['contract'], 'operations': operations,
                         'alObject': view.node(owner)['name'] if owner else None,
                         'apiField': view.node(api)['name'] if api else None,
                         'tableField': '%s.%s' % (view.node(fld)['table'], view.node(fld)['name']) if fld else None,
                         'mentionedIn': mentions})
    return by(rows, 'contract', 'alObject', 'apiField')


def contract_pins(view):
    rows = [{'repo': view.node(repo)['name'], 'pinned': props.get('version'),
             'contract': view.node(contract)['name'], 'current': view.node(contract)['version'],
             'drift': props.get('drift')}
            for repo in view.label('Repo') for contract, props in view.out[repo]['PINS']]
    return sorted(rows, key=lambda r: (not r['drift'], r['repo'], r['contract']))


GROUP_BY = {'group_by': "'product' (default) or 'app': count overlap between products or between single apps"}

QUESTIONS = [
    Question('id_collisions', 'Object ID collisions',
             'Which object IDs are used by more than one app?',
             'Per-tenant extensions that declare the same object ID cannot be installed in the same environment. '
             'Give every app its own ID block.',
             ['type', 'id', 'apps', 'objects'], id_collisions, kind='check', cypher='id-collisions.cypher'),
    Question('field_collisions', 'Field collisions',
             'Which fields do different apps add to the same table with the same ID or name?',
             'Either clash stops the second table extension from installing.',
             ['table', 'clash', 'apps', 'fields'], field_collisions, kind='check', cypher='field-collisions.cypher'),
    Question('product_overlap', 'Where products meet',
             'For each pair of products, how many standard objects do both of them extend, subscribe to or use?',
             'The higher the number, the more a customer running both needs them tested together. Test apps are '
             'left out.',
             ['first', 'second', 'shared', 'objects'], product_overlap, params=dict(GROUP_BY),
             cypher='product-overlap.cypher'),
    Question('shared_standard_objects', 'Standard objects touched by several products',
             'Which standard (Microsoft) objects does more than one product extend, subscribe to or use?',
             'Test these first when several products are installed for the same customer. Test apps are left out.',
             ['type', 'object', 'owners', 'touches'], shared_standard_objects, params=dict(GROUP_BY),
             cypher='shared-standard-objects.cypher'),
    Question('shared_events', 'Events with subscribers in several products',
             'Which events do subscribers in more than one product react to?',
             'Subscriber order is not guaranteed, so each subscriber must work whatever the others did before it.',
             ['publisher', 'event', 'field', 'owners', 'subscribers'], shared_events, params=dict(GROUP_BY),
             cypher='shared-events.cypher'),
    Question('features_without_tests', 'Features without tests',
             'Which features does nothing test?',
             'No test procedure is named in the feature\'s test plan and no test codeunit uses any of its objects.',
             ['app', 'feature', 'name', 'linkedObjects'], features_without_tests, kind='check',
             cypher='features-without-tests.cypher'),
    Question('feature_trace', 'Feature trace',
             'What implements a feature, what tests it, and what does it touch?',
             '`via` tells how each object was linked: its src folder, or a mention in the technical docs.',
             ['app', 'name', 'docs', 'objects', 'tests', 'touches'], feature_trace,
             params={'feature': 'feature code, for example FEAT-WGT-001'}, cypher='feature-trace.cypher'),
    Question('contract_coverage', 'Contract coverage',
             'Which contract operations does no AL object serve, and which channels does nothing in BC emit?',
             'The work left to connect the contract to Business Central.',
             ['contract', 'kind', 'name', 'detail'], contract_coverage, kind='check',
             cypher='contract-coverage.cypher'),
    Question('contract_impact', 'Contract change impact',
             'What does a change to one contract property touch?',
             'The operations that carry it, the AL API field it maps to, the table field behind that, and files in '
             'other repositories that mention the operations.',
             ['contract', 'operations', 'alObject', 'apiField', 'tableField', 'mentionedIn'], contract_impact,
             params={'property': 'Schema.property, for example Category.parentId'}, cypher='contract-impact.cypher'),
    Question('contract_pins', 'Contract pins',
             'Is every repository built against the current contract version?',
             'A pinned version that differs from the contract repository\'s version is drift.',
             ['repo', 'pinned', 'contract', 'current', 'drift'], contract_pins, cypher='contract-pins.cypher'),
]
BY_ID = {q.id: q for q in QUESTIONS}


def answer(view, question_id, **params):
    question = BY_ID[question_id]
    unknown = set(params) - set(question.params)
    if unknown:
        raise ValueError('%s does not take %s' % (question_id, ', '.join(sorted(unknown))))
    return question.run(view, **params)


# ------------------------------------------------------------------------------------------------ overview and lookup
def tested_features(view, app):
    """Features of an app that a test plan names or whose objects a test codeunit uses."""
    tested = 0
    for feature in view.targets(app, 'HAS_FEATURE'):
        objects = view.targets(feature, 'IMPLEMENTED_BY')
        if view.sources(feature, 'VERIFIES') or any(
                view.node(user).get('isTest') for obj in objects for user in view.sources(obj, 'USES')):
            tested += 1
    return tested


def overview(view):
    """Products, their apps and what each app contains. A test app is folded into the app it depends on."""
    products = []
    for product in sorted(view.label('Product'), key=lambda r: r[1]):
        apps, test_apps = {}, []
        for repo in view.targets(product, 'HAS_REPO'):
            for app in view.targets(repo, 'CONTAINS'):
                node = view.node(app)
                objects = view.targets(app, 'CONTAINS')
                entry = {'app': node['name'], 'repo': view.node(repo)['name'], 'github': view.node(repo).get('github'),
                         'version': node.get('version'), 'idRanges': node.get('idRanges') or [],
                         'objects': len(objects), 'features': len(view.targets(app, 'HAS_FEATURE')),
                         'featuresTested': tested_features(view, app),
                         'tests': sum(len(view.targets(o, 'HAS_TEST')) for o in objects), 'testApp': None}
                if node.get('isTest'):
                    test_apps.append((app, entry))
                else:
                    apps[app] = entry
        for app, entry in test_apps:
            tested = next((d for d in view.targets(app, 'DEPENDS_ON') if d in apps), None)
            if tested is None:  # a test app whose app is not listed: show it on its own
                apps[app] = dict(entry, testApp=None)
                continue
            target = apps[tested]
            target['tests'] += entry['tests']
            target['testApp'] = {'app': entry['app'], 'idRanges': entry['idRanges'], 'objects': entry['objects'],
                                 'tests': entry['tests']}
        contracts = [view.node(c)['key'] for repo in view.targets(product, 'HAS_REPO')
                     for c in view.targets(repo, 'OWNS')]
        repos = [{'repo': view.node(r)['name'], 'github': view.node(r).get('github'),
                  'description': view.node(r).get('description')} for r in view.targets(product, 'HAS_REPO')]
        products.append({'product': view.node(product)['name'], 'description': view.node(product).get('description'),
                         'repos': sorted(repos, key=lambda r: r['repo']),
                         'apps': sorted(apps.values(), key=lambda a: a['app']), 'contracts': sorted(contracts)})
    standard = [r for r in view.label('Object') if view.node(r).get('origin') == 'standard']
    all_apps = [a for p in products for a in p['apps']]
    return {'products': products,
            'totals': {'apps': len(all_apps), 'testApps': sum(1 for a in all_apps if a['testApp']),
                       'objects': len(view.app_of), 'standardObjectsTouched': len(standard),
                       'features': len(view.label('Feature')),
                       'featuresTested': sum(a['featuresTested'] for a in all_apps),
                       'testProcedures': len(view.label('TestProcedure')),
                       'contracts': len(view.label('Contract'))}}


def find_objects(view, text, object_type=None, limit=25):
    text = text.lower()
    hits = [view.node(r) for r in view.label('Object')
            if text in view.node(r)['name'].lower() and (not object_type or view.node(r)['type'].lower() == object_type.lower())]
    hits.sort(key=lambda n: (n.get('origin') != 'own', len(n['name']), n['name']))
    return [{'type': n['type'], 'name': n['name'], 'id': n.get('id'), 'origin': n.get('origin'), 'app': n.get('app')}
            for n in hits[:limit]]


def object_details(view, object_type, name):
    """One object with everything around it."""
    ref = next((r for r in view.label('Object') if view.node(r)['name'].lower() == name.lower()
                and view.node(r)['type'].lower() == object_type.lower()), None)
    if ref is None:
        return None
    node = dict(view.node(ref))

    def names(refs):
        return sorted('%s %s' % (view.node(r).get('type', r[0]), view.node(r)['name']) for r in set(refs))
    app = view.app_of.get(ref)
    return {
        'object': node,
        'product': view.product_of_app.get(app),
        'extends': names(view.targets(ref, 'EXTENDS')),
        'extendedBy': names(view.sources(ref, 'EXTENDS')),
        'implements': names(view.targets(ref, 'IMPLEMENTS')),
        'uses': names(view.targets(ref, 'USES')),
        'usedBy': names(view.sources(ref, 'USES')),
        'fields': sorted(view.node(f)['name'] for f in view.targets(ref, 'DECLARES') + view.targets(ref, 'ADDS_FIELD')),
        'apiFields': sorted(view.node(f)['name'] for f in view.targets(ref, 'EXPOSES')),
        'subscribesTo': sorted('%s::%s' % (view.node(e)['object'], view.node(e)['name'])
                               for e in view.targets(ref, 'SUBSCRIBES_TO')),
        'publishes': sorted(view.node(e)['name'] for e in view.sources(ref, 'PUBLISHED_BY')),
        'tests': sorted(view.node(t)['name'] for t in view.targets(ref, 'HAS_TEST')),
        'features': sorted(view.node(f)['key'] for f in view.sources(ref, 'IMPLEMENTED_BY')),
        'serves': sorted(view.node(o)['key'] for o in view.targets(ref, 'SERVES')),
        'emits': sorted(view.node(c)['key'] for c in view.targets(ref, 'EMITS')),
    }
