# bc-knowledge-graph

A Neo4j knowledge graph of Microsoft Dynamics 365 Business Central products: AL objects, the standard
objects and events they touch, features, tests, and the API contracts that connect AL extensions to the
systems around them.

It answers questions that are hard to answer by reading repositories one at a time:

| Question | Query |
|---|---|
| Which object IDs are used by more than one of my apps? (per-tenant extensions with the same ID cannot be installed together) | [id-collisions](queries/id-collisions.cypher) |
| Which fields do two apps add to the same table with the same ID or name? | [field-collisions](queries/field-collisions.cypher) |
| Which pairs of products touch the most standard objects in common? | [product-overlap](queries/product-overlap.cypher) |
| Which standard tables, codeunits and events are touched by more than one product? | [shared-standard-objects](queries/shared-standard-objects.cypher), [shared-events](queries/shared-events.cypher) |
| Which features have no tests? | [features-without-tests](queries/features-without-tests.cypher) |
| What implements a feature, what tests it, what standard objects does it touch? | [feature-trace](queries/feature-trace.cypher) |
| Which contract operations and channels have no AL implementation yet? | [contract-coverage](queries/contract-coverage.cypher) |
| If a contract property changes, which AL API field and BC table field are affected? | [contract-impact](queries/contract-impact.cypher) |
| Is every repository built against the current contract version? | [contract-pins](queries/contract-pins.cypher) |

The graph model is described in [docs/graph-model.md](docs/graph-model.md).

**See it live:** [graph.dmom.ai](https://graph.dmom.ai) — the report for a set of public Business Central apps,
rebuilt every night.

## How it works

`bckg extract` reads the repositories listed in `products.yaml` and writes `out/graph.json`:

- **AL apps** — every `app.json` in a repository. The parser reads declarations, not behaviour: object
  headers, table fields, API page and query fields, event subscribers and publishers, test procedures, and
  the objects each file refers to through variables and `Type::"Name"` references. Names that no listed app
  defines become shared *standard* objects, which is what connects products to each other.
- **Features** — `docs/FEAT-<AREA>-<NNN>-<Name>/` folders next to an app. A feature is linked to objects
  in the `src/<Folder>` whose name matches it, and to objects its `technical-documentation.md` quotes in
  backticks. Test procedures quoted in its `test-plan*.md` verify it.
- **Contracts** — OpenAPI 3 and AsyncAPI 3 files in the folders a repository lists under `contracts`.
  AL string literals that equal a channel address count as emitting it. Text files in repositories without
  AL (or with `scan: true`) are searched for operation IDs and channel addresses. `CONTRACT_PIN` files
  are compared with the contract version.
- **Bindings** — the link between a contract operation and the AL API page that serves it, and between
  contract properties and API page fields, is declared in `products.yaml`, because an integration layer
  usually renames fields on purpose.

Everything after that works from `out/graph.json`, without Neo4j:

- `bckg ask` answers one question in the terminal,
- `bckg report` writes one self-contained HTML page that answers every question,
- `bckg mcp` serves the questions to Claude (or any MCP client), so you can ask in plain language.

Each question is implemented once in [`bckg/questions.py`](bckg/questions.py) and has a Cypher twin in
`queries/` for Neo4j Browser; a test checks that both return the same rows. Neo4j is optional: load the graph
with `bckg load` to explore it visually or to ask free-form Cypher questions.

## Setup

Requires Python 3.10+. Neo4j 5.23 or later is optional.

```sh
python -m venv .venv
.venv/Scripts/pip install -e ".[mcp]"     # Windows; use .venv/bin/pip elsewhere. Drop [mcp] if you do not need it.
cp products.example.yaml products.yaml    # list your products and repositories
cp .env.example .env                      # only for Neo4j: set NEO4J_PASSWORD
docker compose up -d                      # only for Neo4j: http://localhost:7474 and bolt://localhost:7687
```

`products.yaml`, `.env`, `out/` and `.cache/` are gitignored: they name your repositories and contain your
code's structure.

## Use

```sh
bckg extract                                   # writes out/graph.json and prints counts and warnings
bckg ask                                       # lists the questions
bckg ask id_collisions
bckg ask feature_trace --param feature=FEAT-WGT-001
bckg report                                    # writes out/report.html
bckg report --intro intro.html --outro outro.html   # your own introduction and closing section (HTML fragments)
```

### Ask Claude

`bckg mcp` is an MCP server over stdio. Register it with Claude Code from this folder:

```sh
claude mcp add bc-knowledge-graph -- .venv/Scripts/bckg mcp --graph out/graph.json
```

(or add the same command to any MCP client's configuration). Then ask, for example, *"Can the warehouse and
construction apps be installed in the same environment?"* or *"What does FEAT-WGT-001 consist of?"*. The server
offers one tool per question, `overview`, `find_objects`, `object_details` and `write_report`, plus the graph model
as a resource. It rereads `out/graph.json` when it changes, so `bckg extract` is enough to refresh its answers.
With `NEO4J_PASSWORD` set it also offers a read-only `cypher` tool (writes are rejected by the database).

### Neo4j (optional)

```sh
bckg load                                      # replaces the database content with out/graph.json
bckg query queries/id-collisions.cypher
bckg query queries/feature-trace.cypher --param feature=FEAT-WGT-001
```

The same queries run in Neo4j Browser (`http://localhost:7474`); set parameters there with
`:param feature => 'FEAT-WGT-001'`.

Warnings name features that no object could be linked to. Assign their folder in `products.yaml`:

```yaml
feature_folders:
  "My App:FEAT-RPT-002": Reporting
```

## Development

```sh
.venv/Scripts/pip install -e ".[dev]"
.venv/Scripts/python -m pytest
```

The tests run against an invented two-product example under `tests/fixtures`. The parity tests (Python questions
against their Cypher twins) run only when `NEO4J_TEST_URI` and `NEO4J_TEST_PASSWORD` point at a **throwaway**
Neo4j, because they replace its content; CI provides one.

## Showcase

[`showcase/products.yaml`](showcase/products.yaml) lists public repositories. The
[Showcase workflow](.github/workflows/showcase.yml) extracts them every night, writes the report and publishes it,
together with the graph file, with GitHub Pages at [graph.dmom.ai](https://graph.dmom.ai).

## Licence

[MIT](LICENSE)
