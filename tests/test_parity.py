"""Every Python question returns the same rows as its Cypher twin in queries/.

Needs a disposable Neo4j, because loading replaces the database content:
    NEO4J_TEST_URI=bolt://localhost:7687 NEO4J_TEST_PASSWORD=... pytest tests/test_parity.py
NEO4J_TEST_GRAPH may point at another out/graph.json to compare on real data. CI runs this against a Neo4j service.
"""
import json
import os
from pathlib import Path

import pytest

from bckg.extract import extract
from bckg.graph import Graph
from bckg.questions import QUESTIONS, View

URI = os.environ.get('NEO4J_TEST_URI')
pytestmark = pytest.mark.skipif(not URI, reason='set NEO4J_TEST_URI to a disposable Neo4j to run parity tests')

FIXTURES = Path(__file__).parent / 'fixtures'
QUERIES = Path(__file__).parent.parent / 'queries'
PARAMS = {'feature_trace': {'feature': os.environ.get('NEO4J_TEST_FEATURE', 'FEAT-WGT-001')},
          'contract_impact': {'property': os.environ.get('NEO4J_TEST_PROPERTY', 'Widget.title')}}


def canonical(value):
    """Order-insensitive form: lists are sorted, so collect() order does not matter."""
    if isinstance(value, dict):
        return {k: canonical(v) for k, v in sorted(value.items())}
    if isinstance(value, list):
        return sorted((canonical(v) for v in value), key=lambda v: json.dumps(v, sort_keys=True, default=str))
    return value


def rowset(rows):
    return sorted(json.dumps(canonical(r), sort_keys=True, default=str) for r in rows)


@pytest.fixture(scope='module')
def loaded():
    from bckg.load import load
    graph_file = os.environ.get('NEO4J_TEST_GRAPH')
    graph = Graph.load(Path(graph_file)) if graph_file else extract(FIXTURES / 'products.yaml')[0]
    load(graph, URI, os.environ.get('NEO4J_TEST_USER', 'neo4j'), os.environ['NEO4J_TEST_PASSWORD'])
    return View(graph)


@pytest.mark.parametrize('question', [q for q in QUESTIONS if q.cypher], ids=lambda q: q.id)
def test_python_matches_cypher(loaded, question):
    from bckg.load import query
    params = PARAMS.get(question.id, {})
    keys, rows = query(QUERIES / question.cypher, URI, os.environ.get('NEO4J_TEST_USER', 'neo4j'),
                       os.environ['NEO4J_TEST_PASSWORD'], params=params)
    cypher_rows = [dict(zip(keys, row)) for row in rows]
    python_rows = question.run(loaded, **params)
    assert keys == question.columns
    assert rowset(python_rows) == rowset(cypher_rows)
