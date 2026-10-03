# bc-knowledge-graph

Python extractor that turns Business Central products (AL apps, feature docs, tests, OpenAPI/AsyncAPI
contracts) into a Neo4j graph. Read `README.md` for usage and `docs/graph-model.md` for the model.

## Rules

- **This repository is public.** Never commit anything taken from the products it reads: no graph exports
  (`out/`), no cloned sources (`.cache/`), no real `products.yaml`, no AL copied into fixtures. Test
  fixtures are invented (`tests/fixtures`, apps "Alpha" and "Beta").
- **Only the owner merges pull requests.** Work on a branch created with
  `git checkout -b <branch> --no-track origin/main`, push it, open a PR, and stop there.
- When the extractor learns a new node or relationship, update `docs/graph-model.md` and add a fixture
  case to `tests/test_extract.py`. Saved queries live in `queries/`, one question per file, with a comment
  saying what the question is.

## Layout

| Path | What |
|---|---|
| `bckg/al.py` | AL declaration parser (no compiler needed) |
| `bckg/contracts.py` | OpenAPI 3 / AsyncAPI 3 reader |
| `bckg/extract.py` | products.yaml -> graph: name resolution, features, tests, contract links |
| `bckg/load.py` | graph -> Neo4j (full rebuild), query runner |
| `bckg/cli.py` | `bckg extract | load | query | stats` |
