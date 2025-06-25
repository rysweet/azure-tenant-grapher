// Migration 0003 – Back-fill Subscription nodes & CONTAINS edges

// 1. Create Subscription nodes from ResourceGroup or Resource ids
MATCH (n)
WHERE EXISTS(n.id) AND n.id STARTS WITH '/subscriptions/'
WITH DISTINCT split(n.id,'/')[2] AS subId, n
WITH subId, collect(DISTINCT n) AS nodes
MERGE (s:Subscription {id: subId})
  ON CREATE SET s.name = subId  // use id as name placeholder
WITH s, nodes
UNWIND nodes AS n
  MERGE (s)-[:CONTAINS]->(n);

// 2. Ensure ResourceGroup nodes have subscription_id + name
MATCH (rg:ResourceGroup)
SET rg.subscription_id = split(rg.id,'/')[2],
    rg.name = split(rg.id,'/')[4];

// 3. Ensure Resource nodes have subscription_id & resource_group
MATCH (r:Resource)
WHERE NOT EXISTS(r.subscription_id)
SET r.subscription_id = split(r.id,'/')[2],
    r.resource_group  = split(r.id,'/')[4];

// 4. Update GraphVersion
MERGE (v:GraphVersion {major:3, minor:0})
  ON CREATE
    SET v.appliedAt = datetime();
