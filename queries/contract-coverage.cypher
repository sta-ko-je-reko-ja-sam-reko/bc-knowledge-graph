// Contract operations that no AL object serves yet, and channels that nothing in Business Central emits.
MATCH (c:Contract)-[:DEFINES]->(op:Operation)
WHERE NOT (op)<-[:SERVES]-(:Object)
RETURN c.key AS contract, 'operation' AS kind, op.name AS name, op.method + ' ' + op.path AS detail
UNION
MATCH (c:Contract)-[:DEFINES]->(ch:Channel)
WHERE NOT (ch)<-[:EMITS]-(:Object)
RETURN c.key AS contract, 'channel' AS kind, ch.name AS name, '' AS detail;
