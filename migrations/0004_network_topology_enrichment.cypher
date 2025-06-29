// Network-topology enrichment constraints
CREATE CONSTRAINT private_endpoint_id IF NOT EXISTS
FOR (n:PrivateEndpoint) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT dns_zone_id IF NOT EXISTS
FOR (n:DNSZone) REQUIRE n.id IS UNIQUE;
