// What a change to one contract property touches: the operations that carry it, the AL API field it
// maps to, the table field behind that, and the files in other repositories that mention the operation.
// Parameter, for example:  :param property => 'Category.parentId'
MATCH (schema:Schema)-[:HAS_PROPERTY]->(prop:Property)
WHERE prop.schema + '.' + prop.name = $property
OPTIONAL MATCH (op:Operation)-[:USES_SCHEMA]->(:Schema)-[:HAS_PROPERTY|REFERENCES*0..10]->(schema)
OPTIONAL MATCH (prop)-[:MAPS_TO]->(api:ApiField)<-[:EXPOSES]-(alObject:Object)
OPTIONAL MATCH (api)-[:READS]->(field:Field)
OPTIONAL MATCH (repo:Repo)-[m:MENTIONS]->(op)
RETURN prop.contract AS contract, collect(DISTINCT op.name) AS operations,
       alObject.name AS alObject, api.name AS apiField, field.table + '.' + field.name AS tableField,
       collect(DISTINCT repo.name + ': ' + m.file) AS mentionedIn;
