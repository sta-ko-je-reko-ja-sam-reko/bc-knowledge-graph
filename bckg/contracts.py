"""Read OpenAPI 3 and AsyncAPI 3 specifications into contract nodes.

A contract is identified by its file stem without the version suffix (`shop-api-v1.yaml` ->
`shop-api`) and by `info.version`.
"""
import re

import yaml

HTTP_METHODS = ('get', 'put', 'post', 'delete', 'patch', 'head', 'options')
SCHEMA_REF = re.compile(r'^#/components/schemas/(.+)$')
MESSAGE_REF = re.compile(r'^#/components/messages/(.+)$')


def contract_name(path):
    return re.sub(r'-v\d+$', '', path.stem)


def collect_schema_refs(value, found=None):
    """Every `#/components/schemas/X` referenced anywhere below value."""
    found = set() if found is None else found
    if isinstance(value, dict):
        for key, item in value.items():
            if key == '$ref' and isinstance(item, str) and SCHEMA_REF.match(item):
                found.add(SCHEMA_REF.match(item).group(1))
            else:
                collect_schema_refs(item, found)
    elif isinstance(value, list):
        for item in value:
            collect_schema_refs(item, found)
    return found


def add_schemas(graph, contract, schemas):
    refs = {}
    for name, schema in (schemas or {}).items():
        schema_ref = graph.node('Schema', '%s#%s' % (contract[1], name), name=name, contract=contract[1])
        graph.rel('DEFINES', contract, schema_ref)
        refs[name] = schema_ref
    for name, schema in (schemas or {}).items():
        properties = (schema or {}).get('properties') or {}
        required = set((schema or {}).get('required') or [])
        for prop, definition in properties.items():
            definition = definition or {}
            prop_ref = graph.node('Property', '%s#%s.%s' % (contract[1], name, prop), name=prop, schema=name,
                                  contract=contract[1], dataType=definition.get('type'),
                                  required=prop in required, description=definition.get('description'))
            graph.rel('HAS_PROPERTY', refs[name], prop_ref)
            for target in collect_schema_refs(definition):
                if target in refs:
                    graph.rel('REFERENCES', prop_ref, refs[target])
    return refs


def add_openapi(graph, path, spec, repo):
    contract = graph.node('Contract', '%s@%s' % (contract_name(path), spec['info']['version']),
                          name=contract_name(path), version=spec['info']['version'], kind='openapi',
                          title=spec['info'].get('title'), file=path.as_posix())
    graph.rel('OWNS', repo, contract)
    schemas = add_schemas(graph, contract, (spec.get('components') or {}).get('schemas'))
    for route, item in (spec.get('paths') or {}).items():
        for method in HTTP_METHODS:
            operation = (item or {}).get(method)
            if not operation:
                continue
            operation_id = operation.get('operationId') or '%s %s' % (method.upper(), route)
            op_ref = graph.node('Operation', '%s:%s' % (contract[1], operation_id), name=operation_id,
                                method=method.upper(), path=route, contract=contract[1],
                                summary=operation.get('summary'), tags=operation.get('tags'))
            graph.rel('DEFINES', contract, op_ref)
            request = collect_schema_refs(operation.get('requestBody'))
            response = collect_schema_refs(operation.get('responses'))
            for name in sorted(request | response):
                if name in schemas:
                    graph.rel('USES_SCHEMA', op_ref, schemas[name],
                              direction='request' if name in request else 'response')
    return contract


def add_asyncapi(graph, path, spec, repo):
    contract = graph.node('Contract', '%s@%s' % (contract_name(path), spec['info']['version']),
                          name=contract_name(path), version=spec['info']['version'], kind='asyncapi',
                          title=spec['info'].get('title'), file=path.as_posix())
    graph.rel('OWNS', repo, contract)
    components = spec.get('components') or {}
    schemas = add_schemas(graph, contract, components.get('schemas'))
    messages = {}
    for name, message in (components.get('messages') or {}).items():
        message_ref = graph.node('Message', '%s:%s' % (contract[1], name), name=name, contract=contract[1],
                                 summary=(message or {}).get('summary'))
        graph.rel('DEFINES', contract, message_ref)
        messages[name] = message_ref
        for target in collect_schema_refs((message or {}).get('payload')):
            if target in schemas:
                graph.rel('USES_SCHEMA', message_ref, schemas[target])
    for name, channel in (spec.get('channels') or {}).items():
        address = (channel or {}).get('address') or name
        channel_ref = graph.node('Channel', '%s:%s' % (contract[1], address), name=address, contract=contract[1])
        graph.rel('DEFINES', contract, channel_ref)
        for message in ((channel or {}).get('messages') or {}).values():
            match = MESSAGE_REF.match((message or {}).get('$ref', ''))
            if match and match.group(1) in messages:
                graph.rel('CARRIES', channel_ref, messages[match.group(1)])
    return contract


def add_contracts(graph, root, folder, repo):
    """Load every OpenAPI/AsyncAPI document below root/folder."""
    contracts = []
    for path in sorted((root / folder).rglob('*.y*ml')):
        spec = yaml.safe_load(path.read_text(encoding='utf-8'))
        if not isinstance(spec, dict) or 'info' not in spec:
            continue
        relative = path.relative_to(root)
        if 'openapi' in spec:
            contracts.append(add_openapi(graph, relative, spec, repo))
        elif 'asyncapi' in spec:
            contracts.append(add_asyncapi(graph, relative, spec, repo))
    return contracts
