// For each pair of products, the standard objects both of them extend, subscribe to or use (test apps left out).
// The higher the number, the more a customer running both needs them tested together.
MATCH (p:Product)-[:HAS_REPO]->(:Repo)-[:CONTAINS]->(a:App)-[:CONTAINS]->(o:Object)
WHERE coalesce(a.isTest, false) = false
MATCH (o)-[:EXTENDS|USES|SUBSCRIBES_TO]->(x)
OPTIONAL MATCH (x:Event)-[:PUBLISHED_BY]->(publisher:Object)
WITH p.name AS owner, CASE WHEN x:Event THEN publisher ELSE x END AS target
WHERE target.origin = 'standard'
WITH DISTINCT owner, target
WITH target, collect(owner) AS owners
UNWIND owners AS first
UNWIND owners AS second
WITH first, second, target
WHERE first < second
WITH first, second, collect(target.type + ' ' + target.name) AS objects
RETURN first, second, size(objects) AS shared, objects
ORDER BY shared DESC, first, second;
