"""Write a Graph to Neo4j.

The graph is derived data, so a load replaces what is in the database: it deletes every node and writes
the new graph in batches. Objects also get their AL type as a second label (`:Object:Table`), so queries
can say `MATCH (t:Table)`.
"""
from collections import defaultdict

from neo4j import GraphDatabase

from .al import OBJECT_TYPES

BATCH = 1000
LABELS = ('Product', 'Repo', 'App', 'Object', 'Field', 'ApiField', 'Event', 'Feature', 'TestProcedure',
          'Contract', 'Operation', 'Schema', 'Property', 'Channel', 'Message')


def batches(rows):
    for start in range(0, len(rows), BATCH):
        yield rows[start:start + BATCH]


def check_identifier(name):
    if not name.replace('_', '').isalnum():
        raise ValueError('unexpected label or relationship type: %r' % name)
    return name


def load(graph, uri, user, password, database=None):
    driver = GraphDatabase.driver(uri, auth=(user, password), notifications_min_severity='OFF')
    try:
        with driver.session(database=database) as session:
            session.run('MATCH (n) CALL (n) { DETACH DELETE n } IN TRANSACTIONS OF 10000 ROWS').consume()
            for label in LABELS:
                session.run('CREATE CONSTRAINT %s_key IF NOT EXISTS FOR (n:%s) REQUIRE n.key IS UNIQUE'
                            % (label.lower(), label)).consume()

            nodes = defaultdict(list)
            for (label, _), props in graph.nodes.items():
                second = props.get('type') if label == 'Object' else None
                nodes[(label, second if second in OBJECT_TYPES.values() else None)].append(props)
            for (label, second), rows in nodes.items():
                labels = check_identifier(label) + (':' + check_identifier(second) if second else '')
                for batch in batches(rows):
                    session.run('UNWIND $rows AS row MERGE (n:%s {key: row.key}) SET n += row' % labels,
                                rows=batch).consume()

            rels = defaultdict(list)
            for (rel_type, start, end), props in graph.rels.items():
                rels[(rel_type, start[0], end[0])].append({'a': start[1], 'b': end[1], 'props': props})
            for (rel_type, start_label, end_label), rows in rels.items():
                query = ('UNWIND $rows AS row MATCH (a:%s {key: row.a}) MATCH (b:%s {key: row.b}) '
                         'MERGE (a)-[r:%s]->(b) SET r += row.props'
                         % (check_identifier(start_label), check_identifier(end_label), check_identifier(rel_type)))
                for batch in batches(rows):
                    session.run(query, rows=batch).consume()
    finally:
        driver.close()
    return len(graph.nodes), len(graph.rels)


def query(path, uri, user, password, database=None, params=None):
    """Run a saved .cypher file and return its column names and rows."""
    driver = GraphDatabase.driver(uri, auth=(user, password), notifications_min_severity='OFF')
    try:
        records, summary, keys = driver.execute_query(path.read_text(encoding='utf-8'), params or {},
                                                      database_=database)
        return keys, [record.values() for record in records]
    finally:
        driver.close()
