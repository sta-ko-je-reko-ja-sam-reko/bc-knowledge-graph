"""The MCP server, end to end over stdio, as an MCP client sees it."""
import json
import sys
from pathlib import Path

import anyio
import pytest

pytest.importorskip('mcp')
from mcp.client.session import ClientSession  # noqa: E402
from mcp.client.stdio import StdioServerParameters, stdio_client  # noqa: E402

from bckg.extract import extract  # noqa: E402

FIXTURES = Path(__file__).parent / 'fixtures'


@pytest.fixture(scope='module')
def graph_file(tmp_path_factory):
    path = tmp_path_factory.mktemp('mcp') / 'graph.json'
    extract(FIXTURES / 'products.yaml')[0].save(path)
    return path


def session_run(graph_file, steps):
    async def main():
        params = StdioServerParameters(command=sys.executable, args=['-m', 'bckg', 'mcp', '--graph', str(graph_file)],
                                       env={'PYTHONPATH': str(Path(__file__).parent.parent)}, cwd=str(graph_file.parent))
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await steps(session)
    return anyio.run(main)


def payload(result):
    assert not result.is_error, result
    return json.loads(result.content[0].text)


def test_tools_resources_and_answers(graph_file):
    async def steps(session):
        tools = {t.name: t for t in (await session.list_tools()).tools}
        collisions = payload(await session.call_tool('id_collisions', {}))
        trace = payload(await session.call_tool('feature_trace', {'feature': 'FEAT-WGT-001'}))
        details = payload(await session.call_tool('object_details', {'object_type': 'Table', 'name': 'Customer'}))
        found = payload(await session.call_tool('find_objects', {'text': 'widget'}))
        overview = payload(await session.call_tool('overview', {}))
        model = await session.read_resource('bckg://graph-model')
        return tools, collisions, trace, details, found, overview, model

    tools, collisions, trace, details, found, overview, model = session_run(graph_file, steps)
    assert {'overview', 'list_questions', 'id_collisions', 'feature_trace', 'find_objects', 'object_details',
            'write_report'} <= set(tools)
    assert 'cypher' not in tools  # only offered when NEO4J_PASSWORD is set
    assert tools['id_collisions'].annotations.read_only_hint is True
    assert set(tools['feature_trace'].input_schema['required']) == {'feature'}
    assert {'type': 'TableExtension', 'id': 50000, 'apps': ['Alpha', 'Beta'],
            'objects': ['ALP Customer', 'BET Customer']} in collisions['rows']
    assert trace['rows'][0]['tests'] == ['ALP Widget Tests.WidgetIsCreated']
    assert details['object']['origin'] == 'standard'
    assert details['extendedBy'] == ['TableExtension ALP Customer', 'TableExtension BET Customer']
    assert found['objects'][0]['name'] == 'ALP Widget'
    assert overview['totals']['contracts'] == 2
    assert 'Graph model' in model.contents[0].text
