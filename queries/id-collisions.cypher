// Object IDs used by more than one app.
// Per-tenant extensions that declare the same object ID cannot be installed in the same environment.
MATCH (a:App {origin: 'own'})-[:CONTAINS]->(o:Object)
WHERE o.id IS NOT NULL
WITH o.type AS type, o.id AS id, collect(DISTINCT a.name) AS apps, collect(o.name) AS objects
WHERE size(apps) > 1
RETURN type, id, apps, objects
ORDER BY type, id;
