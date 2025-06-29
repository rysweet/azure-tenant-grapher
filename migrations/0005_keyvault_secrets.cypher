// Migration: Add KeyVaultSecret node and STORES_SECRET relationship

// Create KeyVaultSecret node with properties: name, contentType
// (No secret value is ever stored.)

// Example Cypher for documentation, actual node creation is handled by discovery logic
// This migration ensures the label and relationship are documented and constraints can be added if needed.

CREATE CONSTRAINT keyvaultsecret_name_unique IF NOT EXISTS
FOR (s:KeyVaultSecret)
REQUIRE (s.name) IS UNIQUE;

// (Optional) Add contentType index for query performance
CREATE INDEX keyvaultsecret_contentType IF NOT EXISTS
FOR (s:KeyVaultSecret)
ON (s.contentType);

// Relationship documentation (no data created here)
// STORES_SECRET: (KeyVault)-[:STORES_SECRET]->(KeyVaultSecret)
