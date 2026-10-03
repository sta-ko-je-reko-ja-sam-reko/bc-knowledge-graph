// Standard (Microsoft) objects that more than one product extends, subscribes to or uses.
// These are the places to test first when two products are installed for the same customer.
MATCH (p:Product)-[:HAS_REPO]->(:Repo)-[:CONTAINS]->(a:App)-[:CONTAINS]->(o:Object)
WHERE coalesce(a.isTest, false) = false
MATCH (o)-[r:EXTENDS|USES|SUBSCRIBES_TO]->(x)
OPTIONAL MATCH (x:Event)-[:PUBLISHED_BY]->(publisher:Object)
WITH p.name AS owner, type(r) AS how, CASE WHEN x:Event THEN publisher ELSE x END AS target
WHERE target.origin = 'standard'
WITH target, owner, collect(DISTINCT how) AS how
WITH target, collect({owner: owner, how: how}) AS touches
WHERE size(touches) > 1
RETURN target.type AS type, target.name AS object, size(touches) AS owners, touches
ORDER BY owners DESC, object;
