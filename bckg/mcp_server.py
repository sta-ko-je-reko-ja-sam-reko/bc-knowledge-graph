"""bckg mcp: an MCP server that answers questions about the graph for Claude and other MCP clients.

Every question in bckg.questions becomes a tool, next to an overview, object lookup and the report. The graph is
read from out/graph.json and reloaded when that file changes, so `bckg extract` is enough to refresh the answers.
When NEO4J_PASSWORD is set, a read-only `cypher` tool is added for questions the catalog does not cover.
"""
import os
from pathlib import Path

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from . import questions as q
from .graph import Graph
from .report import render

READ_ONLY = ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=False)
MODEL_DOC = Path(__file__).resolve().parent.parent / 'docs' / 'graph-model.md'
INSTRUCTIONS = """Knowledge graph of Business Central AL apps: objects, the standard (Microsoft) objects and events they
touch, features, tests and API contracts. Start with `overview`. Use the question tools for the common questions
(ID and field collisions, overlap between products, untested features, contract coverage and impact),
`find_objects` and `object_details` to look at single objects, and the `bckg://graph-model` resource for the node and
relationship names. Answers come from AL declarations only: the graph knows that a codeunit uses a table, not what
it does with it."""


class GraphSource:
    """The graph file, reloaded when it changes on disk."""

    def __init__(self, path):
        self.path = Path(path)
        self._mtime = None
        self._view = None

    def view(self):
        mtime = self.path.stat().st_mtime
        if mtime != self._mtime:
            self._view = q.View(Graph.load(self.path))
            self._mtime = mtime
        return self._view


def question_tool(source, question):
    """A tool function whose signature matches the question's parameters (the SDK builds the schema from it)."""
    def run(**params):
        return {'question': question.ask, 'rows': q.answer(source.view(), question.id, **params)}
    params = set(question.params)
    if params == {'group_by'}:
        def tool(group_by: str = 'product') -> dict:
            return run(group_by=group_by)
    elif params == {'feature'}:
        def tool(feature: str) -> dict:
            return run(feature=feature)
    elif params == {'property'}:
        def tool(property: str) -> dict:
            return run(property=property)
    elif not params:
        def tool() -> dict:
            return run()
    else:
        raise ValueError('no tool signature for parameters %s' % sorted(params))
    return tool


def build(graph_path, neo4j=None):
    source = GraphSource(graph_path)
    server = MCPServer(name='bc-knowledge-graph', instructions=INSTRUCTIONS)

    @server.tool(annotations=READ_ONLY)
    def overview() -> dict:
        """Products, their apps (version, ID ranges, object, feature and test counts) and totals."""
        return q.overview(source.view())

    @server.tool(annotations=READ_ONLY)
    def list_questions() -> dict:
        """The questions the graph answers directly, with their parameters."""
        return {'questions': [{'tool': x.id, 'title': x.title, 'ask': x.ask, 'explain': x.explain, 'params': x.params,
                 'kind': x.kind} for x in q.QUESTIONS]}

    for question in q.QUESTIONS:
        doc = '%s %s' % (question.ask, question.explain)
        if question.params:
            doc += ' Parameters: ' + '; '.join('%s: %s' % kv for kv in question.params.items()) + '.'
        if question.kind == 'check':
            doc += ' An empty result is the good outcome.'
        server.add_tool(question_tool(source, question), name=question.id, title=question.title, description=doc,
                        annotations=READ_ONLY)

    @server.tool(annotations=READ_ONLY)
    def find_objects(text: str, object_type: str = '', limit: int = 25) -> dict:
        """Objects whose name contains `text` (case-insensitive), own objects first. Optionally filter by AL type
        (Table, Page, Codeunit, TableExtension, ...)."""
        return {'objects': q.find_objects(source.view(), text, object_type or None, limit)}

    @server.tool(annotations=READ_ONLY)
    def object_details(object_type: str, name: str) -> dict:
        """One object and everything around it: what it extends and is extended by, uses and is used by, its fields,
        API fields, event subscriptions, tests, features and contract links."""
        details = q.object_details(source.view(), object_type, name)
        return details or {'error': 'no %s named %r; try find_objects' % (object_type, name)}

    @server.tool(annotations=ToolAnnotations(readOnlyHint=False, idempotentHint=True, openWorldHint=False))
    def write_report(path: str = 'out/report.html', group_by: str = 'product') -> dict:
        """Write the HTML report that answers every question without parameters, and return where it is."""
        target = Path(path).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render(source.view(), group_by=group_by, source=str(source.path)), encoding='utf-8')
        return {'report': str(target)}

    @server.resource('bckg://graph-model', name='graph-model', mime_type='text/markdown',
                     description='Node labels, relationship types and properties of the graph.')
    def graph_model() -> str:
        return MODEL_DOC.read_text(encoding='utf-8') if MODEL_DOC.exists() else 'See docs/graph-model.md.'

    if neo4j:
        from neo4j import GraphDatabase, READ_ACCESS
        from neo4j.exceptions import ClientError

        @server.tool(annotations=READ_ONLY)
        def cypher(query: str, limit: int = 200) -> dict:
            """Run a read-only Cypher query against the loaded Neo4j graph (see the bckg://graph-model resource).
            Writes are rejected by the database. At most `limit` rows are returned."""
            driver = GraphDatabase.driver(neo4j['uri'], auth=(neo4j['user'], neo4j['password']),
                                          notifications_min_severity='OFF')
            try:
                with driver.session(database=neo4j.get('database'), default_access_mode=READ_ACCESS) as session:
                    result = session.run(query)
                    keys = result.keys()
                    rows = [record.data() for _, record in zip(range(limit), result)]
                    return {'columns': keys, 'rows': rows, 'truncated': len(rows) == limit}
            except ClientError as error:  # syntax errors and rejected writes: tell the caller why
                return {'error': error.message, 'code': error.code}
            finally:
                driver.close()
    return server


def serve(graph_path, transport='stdio', host='127.0.0.1', port=8765):
    neo4j = None
    if os.environ.get('NEO4J_PASSWORD'):
        neo4j = {'uri': os.environ.get('NEO4J_URI', 'bolt://localhost:7687'),
                 'user': os.environ.get('NEO4J_USER', 'neo4j'), 'password': os.environ['NEO4J_PASSWORD'],
                 'database': os.environ.get('NEO4J_DATABASE')}
    server = build(graph_path, neo4j)
    if transport == 'stdio':
        server.run('stdio')
    else:
        server.run('streamable-http', host=host, port=port)
