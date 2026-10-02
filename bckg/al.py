"""Parse AL source files into plain dictionaries.

The parser reads declarations, not behaviour: the object header, table fields, API page and query
fields, event subscribers and publishers, test procedures, and the objects a file refers to through
variables or `Type::"Name"` references. It strips comments first so commented-out code does not count.
"""
import re

OBJECT_TYPES = {
    name.lower(): name for name in (
        'Table', 'TableExtension', 'Page', 'PageExtension', 'Codeunit', 'Report', 'ReportExtension', 'Query',
        'XmlPort', 'Enum', 'EnumExtension', 'Interface', 'PermissionSet', 'PermissionSetExtension', 'Profile',
        'ControlAddIn', 'Entitlement')
}
EXTENDS_TARGET = {
    'TableExtension': 'Table', 'PageExtension': 'Page', 'ReportExtension': 'Report', 'EnumExtension': 'Enum',
    'PermissionSetExtension': 'PermissionSet',
}
# `Type::"Name"` and variable types, mapped to the object type they point at.
REFERENCE_TYPES = {
    'database': 'Table', 'record': 'Table', 'codeunit': 'Codeunit', 'page': 'Page', 'testpage': 'Page',
    'report': 'Report', 'testrequestpage': 'Report', 'query': 'Query', 'xmlport': 'XmlPort', 'enum': 'Enum',
    'interface': 'Interface', 'table': 'Table',
}
TRIGGER_EVENT = re.compile(r'^On(After|Before)(Insert|Modify|Delete|Rename|Validate)Event$', re.I)

NAME = r'("[^"]+"|[A-Za-z_][\w]*)'
OBJECT_HEADER = re.compile(
    r'^\s*(%s)\s+(?:(\d+)\s+)?%s(?:\s+extends\s+%s)?(?:\s+implements\s+([^\r\n{]+))?'
    % ('|'.join(OBJECT_TYPES), NAME, NAME), re.I | re.M)
NAMESPACE = re.compile(r'^\s*namespace\s+([\w.]+)\s*;', re.M)
PROPERTY = re.compile(r'^\s*(\w+)\s*=\s*([^;\r\n]+);', re.M)
TABLE_FIELD = re.compile(r'\bfield\(\s*(\d+)\s*;\s*%s\s*;\s*([^)\r\n]*?)\s*\)' % NAME, re.I)
PAGE_FIELD = re.compile(r'\bfield\(\s*%s\s*;\s*([^)\r\n]+?)\s*\)' % NAME, re.I)
REC_FIELD = re.compile(r'^Rec\.%s$' % NAME, re.I)
DATAITEM = re.compile(r'\bdataitem\(\s*%s\s*;\s*%s\s*\)' % (NAME, NAME), re.I)
COLUMN = re.compile(r'\b(?:column|filter)\(\s*%s\s*;\s*%s\s*\)' % (NAME, NAME), re.I)
ATTRIBUTE_ARGS = r'\(([^\]]*)\)\]'
SUBSCRIBER = re.compile(r'\[EventSubscriber' + ATTRIBUTE_ARGS + r'\s*(?:\[[^\]]*\]\s*)*'
                        r'(?:local\s+|internal\s+)?procedure\s+%s' % NAME, re.I)
PUBLISHER = re.compile(r'\[(IntegrationEvent|BusinessEvent|InternalEvent|ExternalBusinessEvent)' + ATTRIBUTE_ARGS
                       + r'\s*(?:\[[^\]]*\]\s*)*(?:local\s+|internal\s+)?procedure\s+%s' % NAME, re.I)
TEST = re.compile(r'\[Test\]\s*(?:\[[^\]]*\]\s*)*(?:local\s+|internal\s+)?procedure\s+%s' % NAME, re.I)
VARIABLE = re.compile(r'%s\s*:\s*(Record|Codeunit|Page|TestPage|Report|TestRequestPage|Query|XmlPort|Enum|Interface)'
                      r'\s+%s' % (NAME, NAME), re.I)
TYPE_REFERENCE = re.compile(r'\b(Database|Codeunit|Page|Report|Query|XmlPort|Enum)::%s' % NAME, re.I)
STRING = re.compile(r"'((?:[^']|'')*)'")
DOTTED_LITERAL = re.compile(r'^[a-z][\w-]*(\.[\w-]+)+$')


def unquote(name):
    name = name.strip()
    if len(name) >= 2 and name[0] == name[-1] and name[0] in '"\'':
        return name[1:-1]
    return name


def strip_comments(text):
    """Remove // and /* */ comments, keeping string literals and quoted identifiers intact."""
    out = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in '\'"':
            j = i + 1
            while j < n and text[j] != '\n':
                if text[j] == c:
                    if c == "'" and text.startswith("''", j):
                        j += 2
                        continue
                    break
                j += 1
            out.append(text[i:j + 1])
            i = j + 1
        elif text.startswith('//', i):
            while i < n and text[i] != '\n':
                i += 1
        elif text.startswith('/*', i):
            end = text.find('*/', i + 2)
            block = text[i:] if end < 0 else text[i:end + 2]
            out.append('\n' * block.count('\n'))
            i = n if end < 0 else end + 2
        else:
            out.append(c)
            i += 1
    return ''.join(out)


def split_args(args):
    """Split attribute arguments on commas outside quotes."""
    parts, current, quote = [], [], None
    for c in args:
        if quote:
            current.append(c)
            if c == quote:
                quote = None
        elif c in '\'"':
            quote = c
            current.append(c)
        elif c == ',':
            parts.append(''.join(current).strip())
            current = []
        else:
            current.append(c)
    parts.append(''.join(current).strip())
    return parts


def parse_reference(arg):
    """`Database::"Sales Header"` -> ('Table', 'Sales Header')."""
    match = re.match(r'(\w+)::%s' % NAME, arg.strip())
    if not match:
        return None
    return REFERENCE_TYPES.get(match.group(1).lower(), match.group(1)), unquote(match.group(2))


def event_key(object_type, object_name, event, element=''):
    suffix = "('%s')" % element if element else ''
    return '%s:%s::%s%s' % (object_type, object_name, event, suffix)


def parse(text):
    """Return the object declared in an AL file, or None when the file declares no object."""
    code = strip_comments(text)
    header = OBJECT_HEADER.search(code)
    if not header:
        return None
    object_type = OBJECT_TYPES[header.group(1).lower()]
    obj = {
        'type': object_type,
        'id': int(header.group(2)) if header.group(2) else None,
        'name': unquote(header.group(3)),
        'namespace': (NAMESPACE.search(code) or [None, None])[1],
        'extends': None,
        'implements': [],
        'properties': {},
        'fields': [],
        'api_fields': [],
        'subscriptions': [],
        'publishers': [],
        'tests': [],
        'references': set(),
        'literals': set(),
    }
    if header.group(4):
        obj['extends'] = (EXTENDS_TARGET.get(object_type, object_type), unquote(header.group(4)))
    if header.group(5):
        obj['implements'] = [unquote(name) for name in header.group(5).split(',') if name.strip()]

    body = code[header.end():]
    for match in PROPERTY.finditer(body):
        obj['properties'].setdefault(match.group(1), unquote(match.group(2)))

    if object_type in ('Table', 'TableExtension'):
        for match in TABLE_FIELD.finditer(body):
            obj['fields'].append({'id': int(match.group(1)), 'name': unquote(match.group(2)),
                                  'data_type': match.group(3).strip()})
    elif object_type == 'Page' and obj['properties'].get('PageType', '').lower() == 'api':
        source_table = obj['properties'].get('SourceTable')
        for match in PAGE_FIELD.finditer(body):
            source = REC_FIELD.match(match.group(2).strip())
            obj['api_fields'].append({'name': unquote(match.group(1)), 'table': source_table if source else None,
                                      'field': unquote(source.group(1)) if source else None})
    elif object_type == 'Query' and obj['properties'].get('QueryType', '').lower() == 'api':
        items = [(m.start(), unquote(m.group(2))) for m in DATAITEM.finditer(body)]
        for match in COLUMN.finditer(body):
            table = next((name for start, name in reversed(items) if start < match.start()), None)
            obj['api_fields'].append({'name': unquote(match.group(1)), 'table': table,
                                      'field': unquote(match.group(2))})

    for match in SUBSCRIBER.finditer(body):
        args = split_args(match.group(1))
        target = parse_reference(args[1]) if len(args) > 1 else None
        if not target:
            continue
        event = unquote(args[2]) if len(args) > 2 else ''
        element = unquote(args[3]) if len(args) > 3 else ''
        if not TRIGGER_EVENT.match(event):
            element = ''
        obj['subscriptions'].append({'object': target, 'event': event, 'element': element,
                                     'procedure': unquote(match.group(2))})

    for match in PUBLISHER.finditer(body):
        obj['publishers'].append({'event': unquote(match.group(3)), 'kind': match.group(1)})

    if obj['properties'].get('Subtype', '').lower() == 'test':
        obj['tests'] = [unquote(match.group(1)) for match in TEST.finditer(body)]

    references = SUBSCRIBER.sub('', body)
    for match in VARIABLE.finditer(references):
        obj['references'].add((REFERENCE_TYPES[match.group(2).lower()], unquote(match.group(3))))
    for match in TYPE_REFERENCE.finditer(references):
        obj['references'].add((REFERENCE_TYPES[match.group(1).lower()], unquote(match.group(2))))
    for key in ('SourceTable', 'TableNo'):
        if key in obj['properties']:
            obj['references'].add(('Table', obj['properties'][key]))
    obj['references'].discard((object_type, obj['name']))

    for match in STRING.finditer(body):
        literal = match.group(1)
        if DOTTED_LITERAL.match(literal):
            obj['literals'].add(literal)
    return obj
