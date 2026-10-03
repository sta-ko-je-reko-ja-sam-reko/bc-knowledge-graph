// Events that subscribers in more than one product react to. Subscriber order is not guaranteed,
// so each subscriber must work whatever the other products did before it.
MATCH (p:Product)-[:HAS_REPO]->(:Repo)-[:CONTAINS]->(:App)-[:CONTAINS]->(o:Object)-[s:SUBSCRIBES_TO]->(e:Event)
WITH e, collect(DISTINCT p.name) AS owners, collect(o.name + '.' + s.procedure) AS subscribers
WHERE size(owners) > 1
RETURN e.object AS publisher, e.name AS event, e.element AS field, owners, subscribers
ORDER BY size(owners) DESC, publisher, event;
