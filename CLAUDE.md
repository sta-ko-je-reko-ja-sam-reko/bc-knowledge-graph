# bc-knowledge-graph

Python extractor that turns Business Central products (AL apps, feature docs, tests, OpenAPI/AsyncAPI
contracts) into a Neo4j graph. Read `README.md` for usage and `docs/graph-model.md` for the model.

## Rules

- **This repository is public.** Never commit anything taken from the products it reads: no graph exports
  (`out/`), no cloned sources (`.cache/`), no real `products.yaml`, no AL copied into fixtures. Test
  fixtures are invented (`tests/fixtures`, apps "Alpha" and "Beta").
- **Only the owner merges pull requests.** Work on a branch created with
  `git checkout -b <branch> --no-track origin/main`, push it, open a PR, and stop there.
- A new question goes into `QUESTIONS` in `bckg/questions.py` **and** gets a Cypher twin in `queries/` with the
  same columns; `tests/test_parity.py` checks they agree. Questions without parameters appear in the report and
  every question becomes an MCP tool automatically.
- The showcase lists only repositories that are public. A private product may appear only as a hand-written card in
  `showcase/products-extra.html`, with what the owner approved for publication (features, counts, a link) and never
  its code or structure.
- When the extractor learns a new node or relationship, update `docs/graph-model.md` and add a fixture
  case to `tests/test_extract.py`. Saved queries live in `queries/`, one question per file, with a comment
  saying what the question is.

## Layout

| Path | What |
|---|---|
| `bckg/al.py` | AL declaration parser (no compiler needed) |
| `bckg/contracts.py` | OpenAPI 3 / AsyncAPI 3 reader |
| `bckg/extract.py` | products.yaml -> graph: name resolution, features, tests, contract links |
| `bckg/questions.py` | the question catalog, answered in Python from `out/graph.json`; each has a Cypher twin in `queries/` |
| `bckg/report.py` | self-contained HTML report of every question without parameters |
| `bckg/mcp_server.py` | MCP server: one tool per question, overview, object lookup, report, optional read-only Cypher |
| `bckg/load.py` | graph -> Neo4j (full rebuild), query runner |
| `bckg/cli.py` | `bckg extract | ask | report | mcp | load | query | stats` |
| `showcase/` | public repositories published to graph.dmom.ai (on changes to main or by hand) by `.github/workflows/showcase.yml` |
