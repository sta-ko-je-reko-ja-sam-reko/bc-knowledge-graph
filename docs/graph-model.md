# Graph model

Every node has a unique `key`. Objects also carry their AL type as a second label, so `MATCH (t:Table)`
and `MATCH (c:Codeunit)` work.

## Products and apps

```
(:Product)-[:HAS_REPO]->(:Repo)-[:CONTAINS]->(:App)-[:CONTAINS]->(:Object)
(:App)-[:DEPENDS_ON {version}]->(:App)
(:App)-[:HAS_FEATURE]->(:Feature)
(:Repo)-[:OWNS]->(:Contract)
```

| Label | Key | Properties |
|---|---|---|
| Product | name | name, description |
| Repo | name | name, github, description |
| App | app id | name, publisher, version, runtime, application, target, path, idRanges, origin (`own` for listed apps), isTest |

## AL objects

```
(:Object)-[:EXTENDS]->(:Object)                     tableextension -> table, pageextension -> page, ...
(:Object)-[:IMPLEMENTS]->(:Object:Interface)
(:Object)-[:USES]->(:Object)                        variables, Type::"Name", SourceTable, TableNo
(:Object:Table)-[:DECLARES]->(:Field)
(:Object:TableExtension)-[:ADDS_FIELD]->(:Field)
(:Field)-[:OF_TABLE]->(:Object:Table)
(:Object)-[:EXPOSES]->(:ApiField)-[:READS]->(:Field) API pages and API queries
(:Object)-[:SUBSCRIBES_TO {procedure}]->(:Event)-[:PUBLISHED_BY]->(:Object)
(:Event)-[:ON_FIELD]->(:Field)                      OnAfterValidateEvent / OnBeforeValidateEvent
(:Object)-[:HAS_TEST]->(:TestProcedure)
```

| Label | Key | Properties |
|---|---|---|
| Object | `Type:Name` | type, id, name, namespace, app, folder, file, origin (`own` or `standard`), isTest; API objects add apiPublisher, apiGroup, apiVersion, entityName, entitySetName |
| Field | `Table::Field` | table, name, id, dataType |
| ApiField | `Type:Object::field` | name, object |
| Event | `Type:Object::Event('Element')` | name, object, element, trigger, kind (publishers in listed apps) |
| TestProcedure | `Codeunit::Procedure` | name, codeunit |

An object is `standard` when no listed app declares it: Microsoft base and system objects, and objects of
apps that are not in `products.yaml`. Standard objects are shared nodes, which is what makes cross-product
questions possible.

## Features and tests

```
(:Feature)-[:IMPLEMENTED_BY {via: ['folder', 'docs']}]->(:Object)
(:TestProcedure)-[:VERIFIES {via: ['test-plan']}]->(:Feature)
```

| Label | Key | Properties |
|---|---|---|
| Feature | `App name:FEAT-CODE` | code, name, app, docs |

`via` records how a link was found:

- `folder` — the object is in the `src/<Folder>` that matches the feature's name. A folder that matches
  several features of one app is ambiguous and links to none of them unless `feature_folders` assigns it.
- `docs` — the feature's `technical-documentation.md` quotes the object's name or file name in backticks.
- `test-plan` — the feature's `test-plan*.md` quotes the test procedure's name in backticks.

## Contracts

```
(:Contract)-[:DEFINES]->(:Operation | :Schema | :Channel | :Message)
(:Operation)-[:USES_SCHEMA {direction}]->(:Schema)-[:HAS_PROPERTY]->(:Property)-[:REFERENCES]->(:Schema)
(:Channel)-[:CARRIES]->(:Message)-[:USES_SCHEMA]->(:Schema)
(:Object)-[:SERVES {via: ['binding']}]->(:Operation)
(:Property)-[:MAPS_TO {via: ['binding']}]->(:ApiField)
(:Object)-[:EMITS {via: ['literal']}]->(:Channel)
(:Repo)-[:MENTIONS {file}]->(:Operation | :Channel)
(:Repo)-[:PINS {version, drift}]->(:Contract)
```

| Label | Key | Properties |
|---|---|---|
| Contract | `name@version` | name (file stem without `-vN`), version, kind (`openapi`, `asyncapi`), title, file |
| Operation | `contract:operationId` | name, method, path, summary, tags, contract |
| Schema | `contract#Name` | name, contract |
| Property | `contract#Schema.property` | name, schema, dataType, required, description, contract |
| Channel | `contract:address` | name, contract |
| Message | `contract:Name` | name, summary, contract |
