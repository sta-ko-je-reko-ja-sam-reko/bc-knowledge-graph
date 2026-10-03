// Events that subscribers in more than one product react to. Subscriber order is not guaranteed,
// so each subscriber must work whatever the other products did before it.
MATCH (p:Product)-[:HAS_REPO]->(:Repo)-[:CONTAINS]->(:App)-[:CONTAINS]->(o:Object)-[s:SUBSCRIBES_TO]->(e:Event)
WITH e, collect(DISTINCT p.name) AS products, collect(o.name + '.' + s.procedure) AS subscribers
WHERE size(products) > 1
RETURN e.object AS publisher, e.name AS event, e.element AS field, products, subscribers
ORDER BY size(products) DESC, publisher, event;
