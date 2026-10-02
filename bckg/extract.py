"""Build the graph from the products listed in products.yaml."""
import json
import re
import subprocess
from pathlib import Path

import yaml

from . import al
from .contracts import add_contracts
from .graph import Graph

SKIP_DIRS = {'.git', 'node_modules', '.alpackages', '.cache', '.vscode', '.snapshots', 'dist', 'out', 'generated'}
SCAN_SUFFIXES = {'.ts', '.tsx', '.js', '.mjs', '.cjs', '.bicep', '.json', '.yaml', '.yml', '.cs', '.rs', '.py'}
FEATURE_FOLDER = re.compile(r'^(FEAT-(?:([A-Z]+)-)?\d+)-(.+)$')
BACKTICK = re.compile(r'`([^`\r\n]+)`')
VERSION = re.compile(r'\d+\.\d+\.\d+')


def norm(text):
    return re.sub(r'[^a-z0-9]', '', text.lower())


def walk(root, pattern):
    for path in sorted(root.rglob(pattern)):
        if not SKIP_DIRS.intersection(path.relative_to(root).parts[:-1]):
            yield path


def resolve_repo(repo, config_dir, cache_dir):
    if repo.get('path'):
        return (config_dir / repo['path']).resolve()
    target = cache_dir / repo['name']
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(['gh', 'repo', 'clone', repo['github'], str(target), '--', '--depth', '1', '-q'], check=True)
    return target


class Extractor:
    def __init__(self, config, config_dir, cache_dir):
        self.config = config
        self.config_dir = config_dir
        self.cache_dir = cache_dir
        self.graph = Graph()
        self.parsed = []  # (object ref, parsed dict, app ref, repo ref)
        self.pending_features = []  # (feature ref, folder path, app root, app ref)
        self.test_plans = []  # (feature ref, text, repo ref)
        self.text_scans = []  # (repo ref, root)
        self.pins = []  # (repo ref, version)
        self.warnings = []

    # ---------------------------------------------------------------- products, repos, apps
    def run(self):
        for product in self.config['products']:
            product_ref = self.graph.node('Product', product['name'], name=product['name'])
            for repo in product['repos']:
                root = resolve_repo(repo, self.config_dir, self.cache_dir)
                repo_ref = self.graph.node('Repo', repo['name'], name=repo['name'], github=repo.get('github'))
                self.graph.rel('HAS_REPO', product_ref, repo_ref)
                self.add_repo(repo, root, repo_ref)
        self.resolve_objects()
        self.link_features()
        self.link_tests()
        self.link_contracts()
        return self.graph

    def add_repo(self, repo, root, repo_ref):
        for folder in repo.get('contracts', []):
            add_contracts(self.graph, root, folder, repo_ref)
        pin = root / 'CONTRACT_PIN'
        if pin.exists() and VERSION.search(pin.read_text(encoding='utf-8')):
            self.pins.append((repo_ref, VERSION.search(pin.read_text(encoding='utf-8')).group(0)))
        apps = list(walk(root, 'app.json'))
        for app_json in apps:
            self.add_app(app_json, root, repo_ref)
        if not apps or repo.get('scan'):
            self.text_scans.append((repo_ref, root))

    def add_app(self, app_json, repo_root, repo_ref):
        manifest = json.loads(app_json.read_text(encoding='utf-8-sig'))
        app_root = app_json.parent
        app_ref = self.graph.node('App', manifest['id'], name=manifest['name'], publisher=manifest.get('publisher'),
                                  version=manifest.get('version'), runtime=manifest.get('runtime'),
                                  application=manifest.get('application'), target=manifest.get('target'),
                                  path=app_root.relative_to(repo_root).as_posix(), origin='own',
                                  idRanges=[f"{r['from']}-{r['to']}" for r in manifest.get('idRanges', [])])
        self.graph.rel('CONTAINS', repo_ref, app_ref)
        for dependency in manifest.get('dependencies', []):
            dependency_ref = self.graph.node('App', dependency['id'], name=dependency['name'],
                                             publisher=dependency.get('publisher'))
            self.graph.rel('DEPENDS_ON', app_ref, dependency_ref, version=dependency.get('version'))
        for path in walk(app_root, '*.al'):
            parsed = al.parse(path.read_text(encoding='utf-8-sig'))
            if not parsed:
                continue
            relative = path.relative_to(app_root)
            folder = relative.parts[1] if len(relative.parts) > 2 and relative.parts[0].lower() == 'src' else None
            ref = self.graph.node('Object', '%s:%s' % (parsed['type'], parsed['name']), type=parsed['type'],
                                  id=parsed['id'], name=parsed['name'], namespace=parsed['namespace'], origin='own',
                                  app=manifest['name'], folder=folder,
                                  file=path.relative_to(repo_root).as_posix(),
                                  isTest=bool(parsed['tests']) or None, **api_properties(parsed))
            self.graph.rel('CONTAINS', app_ref, ref)
            self.parsed.append((ref, parsed, app_ref, repo_ref))
            if parsed['tests']:
                self.graph.node('App', manifest['id'], isTest=True)
        docs = app_root / 'docs'
        if docs.is_dir():
            for folder in sorted(p for p in docs.iterdir() if p.is_dir() and FEATURE_FOLDER.match(p.name)):
                match = FEATURE_FOLDER.match(folder.name)
                feature_ref = self.graph.node('Feature', '%s:%s' % (manifest['name'], match.group(1)),
                                              code=match.group(1), name=match.group(3), app=manifest['name'],
                                              docs=folder.relative_to(repo_root).as_posix())
                self.graph.rel('HAS_FEATURE', app_ref, feature_ref)
                self.pending_features.append((feature_ref, folder, app_root, app_ref))
                for plan in folder.glob('test-plan*.md'):
                    self.test_plans.append((feature_ref, plan.read_text(encoding='utf-8'), repo_ref))

    # ---------------------------------------------------------------- names -> objects
    def object_ref(self, object_type, name):
        """The own object of that type and name, or a standard (Microsoft/base) object node."""
        ref = ('Object', '%s:%s' % (object_type, name))
        if not self.graph.has(ref):
            self.graph.node('Object', ref[1], type=object_type, name=name, origin='standard')
        return ref

    def field_ref(self, table, field):
        return self.graph.node('Field', '%s::%s' % (table, field), table=table, name=field)

    def resolve_objects(self):
        for ref, parsed, app_ref, repo_ref in self.parsed:
            table = None
            if parsed['extends']:
                base = self.object_ref(*parsed['extends'])
                self.graph.rel('EXTENDS', ref, base)
                table = parsed['extends'][1] if parsed['extends'][0] == 'Table' else None
            elif parsed['type'] == 'Table':
                table = parsed['name']
            for field in parsed['fields']:
                field_ref = self.field_ref(table, field['name'])
                self.graph.node('Field', field_ref[1], id=field['id'], dataType=field['data_type'])
                self.graph.rel('OF_TABLE', field_ref, self.object_ref('Table', table))
                self.graph.rel('DECLARES' if parsed['type'] == 'Table' else 'ADDS_FIELD', ref, field_ref)
            for interface in parsed['implements']:
                self.graph.rel('IMPLEMENTS', ref, self.object_ref('Interface', interface))
            for api_field in parsed['api_fields']:
                api_ref = self.graph.node('ApiField', '%s::%s' % (ref[1], api_field['name']), name=api_field['name'],
                                          object=parsed['name'])
                self.graph.rel('EXPOSES', ref, api_ref)
                if api_field['table'] and api_field['field']:
                    self.graph.rel('READS', api_ref, self.field_ref(api_field['table'], api_field['field']))
            for subscription in parsed['subscriptions']:
                publisher = self.object_ref(*subscription['object'])
                event_ref = self.graph.node('Event', al.event_key(*subscription['object'], subscription['event'],
                                                                  subscription['element']),
                                            name=subscription['event'], element=subscription['element'] or None,
                                            object=subscription['object'][1],
                                            trigger=bool(al.TRIGGER_EVENT.match(subscription['event'])))
                self.graph.rel('PUBLISHED_BY', event_ref, publisher)
                self.graph.rel('SUBSCRIBES_TO', ref, event_ref, procedure=subscription['procedure'])
                if subscription['element'] and subscription['object'][0] == 'Table':
                    self.graph.rel('ON_FIELD', event_ref, self.field_ref(subscription['object'][1],
                                                                         subscription['element']))
            for publisher in parsed['publishers']:
                event_ref = self.graph.node('Event', al.event_key(parsed['type'], parsed['name'], publisher['event']),
                                            name=publisher['event'], object=parsed['name'], kind=publisher['kind'],
                                            trigger=False)
                self.graph.rel('PUBLISHED_BY', event_ref, ref)
            for test in parsed['tests']:
                test_ref = self.graph.node('TestProcedure', '%s::%s' % (parsed['name'], test), name=test,
                                           codeunit=parsed['name'])
                self.graph.rel('HAS_TEST', ref, test_ref)
            for object_type, name in sorted(parsed['references']):
                self.graph.rel('USES', ref, self.object_ref(object_type, name))

    # ---------------------------------------------------------------- features and tests
    def link_features(self):
        """Link features to objects through their src folder and the object names their technical docs quote.

        A feature gets the folder whose name best matches its own. A folder that matches several features
        of one app (an Invoicing folder holding INV-001 and INV-002) is ambiguous and is linked to none of them, unless
        products.yaml assigns it with feature_folders.
        """
        overrides = self.config.get('feature_folders') or {}
        own = [(ref, parsed, app_ref) for ref, parsed, app_ref, _ in self.parsed]
        guesses = {}
        for feature_ref, folder, _, app_ref in self.pending_features:
            feature = self.graph.nodes[feature_ref]
            folders = {self.graph.nodes[ref].get('folder') for ref, _, a in own if a == app_ref} - {None}
            token = (FEATURE_FOLDER.match(folder.name).group(2) or '').lower()
            name = norm(feature['name'])
            candidates = [f for f in folders if norm(f) and (norm(f) in name or name in norm(f) or norm(f) == token)]
            guesses[feature_ref] = sorted(candidates, key=lambda f: (-len(norm(f)), f))[:1]
        claims = {}
        for feature_ref, chosen in guesses.items():
            for f in chosen:
                claims.setdefault((self.graph.nodes[feature_ref]['app'], f), []).append(feature_ref)
        for feature_ref, folder, app_root, app_ref in self.pending_features:
            feature = self.graph.nodes[feature_ref]
            objects = [(ref, parsed) for ref, parsed, a in own if a == app_ref]
            chosen = overrides.get(feature['key']) or overrides.get(feature['code'])
            chosen = [chosen] if isinstance(chosen, str) else chosen
            if not chosen:
                chosen = [f for f in guesses[feature_ref] if len(claims[(feature['app'], f)]) == 1]
            for ref, _ in objects:
                if self.graph.nodes[ref].get('folder') in chosen:
                    self.graph.rel('IMPLEMENTED_BY', feature_ref, ref, via='folder')
            mentioned = set()
            for doc in folder.glob('technical-documentation*.md'):
                mentioned |= {norm(m) for m in BACKTICK.findall(doc.read_text(encoding='utf-8'))}
            for ref, parsed in objects:
                names = {norm(parsed['name']), norm(Path(self.graph.nodes[ref]['file']).name)}
                if names & mentioned:
                    self.graph.rel('IMPLEMENTED_BY', feature_ref, ref, via='docs')
            if not self.graph.outgoing(feature_ref, 'IMPLEMENTED_BY'):
                self.warnings.append('feature %s: no objects linked (set feature_folders in products.yaml)'
                                     % feature['key'])

    def link_tests(self):
        for feature_ref, text, repo_ref in self.test_plans:
            mentioned = set(BACKTICK.findall(text))
            for ref, node in self.graph.nodes.items():
                if ref[0] == 'TestProcedure' and node['name'] in mentioned:
                    self.graph.rel('VERIFIES', ref, feature_ref, via='test-plan')

    # ---------------------------------------------------------------- contracts
    def link_contracts(self):
        contracts = {node['name']: ref for ref, node in self.graph.nodes.items() if ref[0] == 'Contract'}
        channels = {node['name']: ref for ref, node in self.graph.nodes.items() if ref[0] == 'Channel'}
        operations = {node['name']: ref for ref, node in self.graph.nodes.items() if ref[0] == 'Operation'}
        for ref, parsed, _, _ in self.parsed:
            for literal in sorted(parsed['literals']):
                if literal in channels:
                    self.graph.rel('EMITS', ref, channels[literal], via='literal')
        for repo_ref, root in self.text_scans:
            self.scan_text(repo_ref, root, channels, operations)
        for repo_ref, version in self.pins:
            for name, contract_ref in contracts.items():
                self.graph.rel('PINS', repo_ref, contract_ref, version=version,
                               drift=self.graph.nodes[contract_ref]['version'] != version)
        for binding in self.config.get('bindings') or []:
            self.add_binding(binding, contracts)

    def scan_text(self, repo_ref, root, channels, operations):
        owned = {self.graph.nodes[c]['file'] for c in self.graph.outgoing(repo_ref, 'OWNS')}
        for path in walk(root, '*'):
            relative = path.relative_to(root).as_posix()
            if path.suffix not in SCAN_SUFFIXES or not path.is_file() or relative in owned:
                continue
            text = path.read_text(encoding='utf-8', errors='ignore')
            for name, target in list(channels.items()) + list(operations.items()):
                if re.search(r'(?<![\w.-])%s(?![\w-])' % re.escape(name), text):
                    self.graph.rel('MENTIONS', repo_ref, target, file=relative)

    def add_binding(self, binding, contracts):
        contract_ref = contracts.get(binding['contract'])
        operation_ref = contract_ref and ('Operation', '%s:%s' % (contract_ref[1], binding['operation']))
        object_type, _, object_name = binding['al'].partition(':')
        object_ref = ('Object', '%s:%s' % (al.OBJECT_TYPES[object_type.lower()], object_name))
        if not operation_ref or not self.graph.has(operation_ref) or not self.graph.has(object_ref):
            self.warnings.append('binding %s/%s -> %s: not found' % (binding['contract'], binding['operation'],
                                                                     binding['al']))
            return
        self.graph.rel('SERVES', object_ref, operation_ref, via='binding')
        schema = binding.get('schema')
        for prop, api_field in (binding.get('properties') or {}).items():
            prop_ref = ('Property', '%s#%s.%s' % (contract_ref[1], schema, prop))
            api_ref = ('ApiField', '%s::%s' % (object_ref[1], api_field))
            if self.graph.has(prop_ref) and self.graph.has(api_ref):
                self.graph.rel('MAPS_TO', prop_ref, api_ref, via='binding')
            else:
                self.warnings.append('binding %s.%s -> %s: not found' % (schema, prop, api_field))


def api_properties(parsed):
    props = parsed['properties']
    if props.get('PageType', props.get('QueryType', '')).lower() != 'api':
        return {}
    return {'apiPublisher': props.get('APIPublisher'), 'apiGroup': props.get('APIGroup'),
            'apiVersion': props.get('APIVersion'), 'entityName': props.get('EntityName'),
            'entitySetName': props.get('EntitySetName')}


def extract(config_path, cache_dir=None):
    config_path = Path(config_path).resolve()
    config = yaml.safe_load(config_path.read_text(encoding='utf-8'))
    extractor = Extractor(config, config_path.parent, cache_dir or config_path.parent / '.cache' / 'repos')
    return extractor.run(), extractor.warnings
