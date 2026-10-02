// Features that nothing tests: no test procedure is named in their test plan
// and no test codeunit uses any of their objects.
MATCH (a:App)-[:HAS_FEATURE]->(f:Feature)
WHERE NOT (f)<-[:VERIFIES]-(:TestProcedure)
  AND NOT EXISTS { MATCH (f)-[:IMPLEMENTED_BY]->(:Object)<-[:USES]-(t:Object) WHERE t.isTest }
OPTIONAL MATCH (f)-[:IMPLEMENTED_BY]->(o:Object)
RETURN a.name AS app, f.code AS feature, f.name AS name, count(DISTINCT o) AS linkedObjects
ORDER BY app, feature;
