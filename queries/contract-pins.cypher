// Contract version each repository is pinned to, against the version the contract repository holds.
MATCH (r:Repo)-[p:PINS]->(c:Contract)
RETURN r.name AS repo, p.version AS pinned, c.name AS contract, c.version AS current, p.drift AS drift
ORDER BY drift DESC, repo, contract;
