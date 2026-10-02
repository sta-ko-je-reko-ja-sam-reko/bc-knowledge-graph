// Fields that different apps add to the same table with the same field ID or the same name.
// Either clash stops the second extension from installing.
MATCH (a:App)-[:CONTAINS]->(:Object)-[:ADDS_FIELD]->(f:Field)-[:OF_TABLE]->(t:Object)
WITH t.name AS table, toString(f.id) AS clash, collect(DISTINCT a.name) AS apps, collect(DISTINCT f.name) AS fields
WHERE size(apps) > 1
RETURN table, 'field ID ' + clash AS clash, apps, fields
UNION
MATCH (a:App)-[:CONTAINS]->(:Object)-[:ADDS_FIELD]->(f:Field)-[:OF_TABLE]->(t:Object)
WITH t.name AS table, f.name AS name, collect(DISTINCT a.name) AS apps
WHERE size(apps) > 1
RETURN table, 'field name' AS clash, apps, [name] AS fields;
