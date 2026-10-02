# bc-knowledge-graph

A Neo4j knowledge graph of Microsoft Dynamics 365 Business Central products: AL objects, the standard
objects and events they touch, features, tests, and the API contracts that connect AL extensions to the
systems around them.

It answers questions that are hard to answer by reading repositories one at a time:

| Question | Query |
|---|---|
| Which object IDs are used by more than one of my apps? (per-tenant extensions with the same ID cannot be installed together) | [id-collisions](queries/id-collisions.cypher) |
| Which fields do two apps add to the same table with the same ID or name? | [field-collisions](queries/field-collisions.cypher) |
| Which standard tables, codeunits and events are touched by more than one product? | [shared-standard-objects](queries/shared-standard-objects.cypher), [shared-events](queries/shared-events.cypher) |
| Which features have no tests? | [features-without-tests](queries/features-without-tests.cypher) |
| What implements a feature, what tests it, what standard objects does it touch? | [feature-trace](queries/feature-trace.cypher) |
| Which contract operations and channels have no AL implementation yet? | [contract-coverage](queries/contract-coverage.cypher) |
| If a contract property changes, which AL API field and BC table field are affected? | [contract-impact](queries/contract-impact.cypher) |
| Is every repository built against the current contract version? | [contract-pins](queries/contract-pins.cypher) |

The graph model is described in [docs/graph-model.md](docs/graph-model.md).

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

`bckg load` replaces the content of the Neo4j database with that file. The graph is derived data, so
every load is a full rebuild.

## Setup

Requires Python 3.10+ and Neo4j 5.23 or later.

```sh
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"      # Windows; use .venv/bin/pip elsewhere
cp .env.example .env                      # set NEO4J_PASSWORD
cp products.example.yaml products.yaml    # list your products and repositories
docker compose up -d                      # Neo4j on http://localhost:7474 and bolt://localhost:7687
```

`products.yaml`, `.env`, `out/` and `.cache/` are gitignored: they name your repositories and contain your
code's structure.

## Use

```sh
bckg extract                                   # writes out/graph.json and prints counts and warnings
bckg load                                      # replaces the database content
bckg query queries/id-collisions.cypher
bckg query queries/feature-trace.cypher --param feature=FEAT-WGT-001
bckg query queries/contract-impact.cypher --param property=Category.parentId
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
.venv/Scripts/python -m pytest
```

The tests run against an invented two-product example under `tests/fixtures`.

## Licence

[MIT](LICENSE)
