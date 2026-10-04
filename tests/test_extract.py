from pathlib import Path

import pytest

from bckg.extract import extract
from bckg.graph import Graph

FIXTURES = Path(__file__).parent / 'fixtures'


@pytest.fixture(scope='module')
def result():
    return extract(FIXTURES / 'products.yaml', cache_dir=FIXTURES / '.cache')


@pytest.fixture(scope='module')
def graph(result):
    return result[0]


def rels(graph, rel_type):
    return {(a[1], b[1]) for kind, a, b in graph.rels if kind == rel_type}


def test_products_repos_and_apps(graph):
    assert rels(graph, 'HAS_REPO') == {('Alpha', 'alpha'), ('Beta', 'contracts'), ('Beta', 'beta')}
    apps = {node['name']: node for (label, _), node in graph.nodes.items() if label == 'App'}
    assert apps['Alpha Tests'].get('isTest') is True
    assert apps['Alpha'].get('isTest') is None
    assert ('11111111-1111-1111-1111-222222222222', '11111111-1111-1111-1111-111111111111') in rels(graph, 'DEPENDS_ON')


def test_standard_objects_are_shared_nodes(graph):
    customer = graph.nodes[('Object', 'Table:Customer')]
    assert customer['origin'] == 'standard'
    assert {a for a, b in rels(graph, 'EXTENDS') if b == 'Table:Customer'} == {
        'TableExtension:ALP Customer', 'TableExtension:BET Customer'}


def test_own_objects_resolve_and_comments_do_not_count(graph):
    assert graph.nodes[('Object', 'Table:ALP Widget')]['origin'] == 'own'
    assert ('Codeunit:ALP Sales Subscribers', 'Table:ALP Widget') in rels(graph, 'USES')
    assert not graph.has(('Object', 'Codeunit:Ghost Codeunit'))
    assert not graph.has(('Object', 'Table:Ghost Table'))


def test_fields_from_tables_and_extensions(graph):
    assert ('TableExtension:ALP Customer', 'Customer::ALP Widget Code') in rels(graph, 'ADDS_FIELD')
    assert ('Table:ALP Widget', 'ALP Widget::Code') in rels(graph, 'DECLARES')
    assert graph.nodes[('Field', 'Customer::BET Rating')]['id'] == 50000


def test_events_shared_between_products(graph):
    event = 'Table:Customer::OnAfterValidateEvent(\'Name\')'
    assert {a for a, b in rels(graph, 'SUBSCRIBES_TO') if b == event} == {
        'Codeunit:ALP Sales Subscribers', 'Codeunit:BET Widget Events'}
    assert (event, 'Customer::Name') in rels(graph, 'ON_FIELD')
    assert ('Codeunit:BET Widget Events::OnWidgetChanged', 'Codeunit:BET Widget Events') in rels(graph, 'PUBLISHED_BY')


def test_api_fields_read_table_fields(graph):
    page = graph.nodes[('Object', 'Page:ALP API Widget')]
    assert (page['entitySetName'], page['apiGroup']) == ('widgets', 'alpha')
    assert ('Page:ALP API Widget::description', 'ALP Widget::Description') in rels(graph, 'READS')
    assert ('Query:ALP API Widget Delta::code', 'ALP Widget::Code') in rels(graph, 'READS')
    assert not any(a == 'Page:ALP API Widget::computed' for a, _ in rels(graph, 'READS'))


def test_features_link_through_folders_and_docs(graph):
    links = {b[1]: props['via'] for (kind, a, b), props in graph.rels.items()
             if kind == 'IMPLEMENTED_BY' and a[1] == 'Alpha:FEAT-WGT-001'}
    assert links == {'Table:ALP Widget': ['docs', 'folder'], 'Page:ALP API Widget': ['docs', 'folder'],
                     'Query:ALP API Widget Delta': ['folder'], 'TableExtension:ALP Customer': ['docs']}


def test_feature_folders_can_name_a_nested_folder(graph):
    links = {b[1] for (kind, a, b) in graph.rels if kind == 'IMPLEMENTED_BY' and a[1] == 'Alpha:FEAT-CRD-001'}
    assert links == {'Codeunit:ALP Sales Subscribers'}
    assert graph.nodes[('Object', 'Codeunit:ALP Sales Subscribers')]['srcPath'] == 'Sales/codeunits'


def test_test_plan_links_tests_to_features(graph):
    assert rels(graph, 'VERIFIES') == {('ALP Widget Tests::WidgetIsCreated', 'Alpha:FEAT-WGT-001')}
    assert rels(graph, 'HAS_TEST') == {('Codeunit:ALP Widget Tests', 'ALP Widget Tests::WidgetIsCreated'),
                                       ('Codeunit:ALP Widget Tests', 'ALP Widget Tests::WidgetHasCode')}


def test_contracts_operations_schemas_and_channels(graph):
    assert graph.nodes[('Operation', 'widgets@1.0.0:listWidgets')]['path'] == '/widgets'
    assert ('widgets@1.0.0:listWidgets', 'widgets@1.0.0#WidgetPage') in rels(graph, 'USES_SCHEMA')
    assert ('widgets@1.0.0#WidgetPage.items', 'widgets@1.0.0#Widget') in rels(graph, 'REFERENCES')
    assert ('events@1.0.0:widget.changed', 'events@1.0.0:WidgetChanged') in rels(graph, 'CARRIES')


def test_al_emits_channels_and_bindings_map_properties(graph):
    assert rels(graph, 'EMITS') == {('Codeunit:BET Widget Events', 'events@1.0.0:widget.changed')}
    assert rels(graph, 'SERVES') == {('Page:ALP API Widget', 'widgets@1.0.0:listWidgets')}
    assert rels(graph, 'MAPS_TO') == {('widgets@1.0.0#Widget.id', 'Page:ALP API Widget::systemId'),
                                      ('widgets@1.0.0#Widget.title', 'Page:ALP API Widget::description')}


def test_text_scan_and_contract_pins(graph):
    mentions = rels(graph, 'MENTIONS')
    assert ('contracts', 'widgets@1.0.0:listWidgets') in mentions
    assert ('contracts', 'events@1.0.0:widget.changed') in mentions
    assert not any(b.endswith('deleteWidget') for _, b in mentions)
    pins = {(a[1], b[1]): props for (kind, a, b), props in graph.rels.items() if kind == 'PINS'}
    assert pins[('beta', 'widgets@1.0.0')] == {'version': '0.9.0', 'drift': True}


def test_no_warnings(result):
    assert result[1] == []


def test_json_round_trip(graph, tmp_path):
    path = tmp_path / 'graph.json'
    graph.save(path)
    again = Graph.load(path)
    assert again.nodes == graph.nodes
    assert again.rels == graph.rels
