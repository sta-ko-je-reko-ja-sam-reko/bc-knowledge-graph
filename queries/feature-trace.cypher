// Everything known about one feature. Parameter, for example:  :param feature => 'FEAT-WGT-001'
MATCH (a:App)-[:HAS_FEATURE]->(f:Feature {code: $feature})
OPTIONAL MATCH (f)-[i:IMPLEMENTED_BY]->(o:Object)
OPTIONAL MATCH (t:TestProcedure)-[:VERIFIES]->(f)
OPTIONAL MATCH (o)-[:EXTENDS|SUBSCRIBES_TO]->(x)
RETURN a.name AS app, f.name AS name, f.docs AS docs,
       collect(DISTINCT CASE WHEN o IS NULL THEN null ELSE {object: o.type + ' ' + o.name, via: i.via} END) AS objects,
       collect(DISTINCT t.codeunit + '.' + t.name) AS tests,
       collect(DISTINCT coalesce(x.object + '::' + x.name, x.type + ' ' + x.name)) AS touches;
