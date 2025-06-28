// Migration 0002 – core uniqueness & indexes
// Uniqueness constraints
CREATE CONSTRAINT IF NOT EXISTS
  FOR (r:Resource)
  REQUIRE r.id IS UNIQUE;

CREATE CONSTRAINT IF NOT EXISTS
  FOR (rg:ResourceGroup)
  REQUIRE rg.id IS UNIQUE;

CREATE CONSTRAINT IF NOT EXISTS
  FOR (t:Tag)
  REQUIRE t.id IS UNIQUE;

CREATE CONSTRAINT IF NOT EXISTS
  FOR (reg:Region)
  REQUIRE reg.name IS UNIQUE;

CREATE CONSTRAINT IF NOT EXISTS
  FOR (u:User)
  REQUIRE u.id IS UNIQUE;

CREATE CONSTRAINT IF NOT EXISTS
  FOR (sp:ServicePrincipal)
  REQUIRE sp.id IS UNIQUE;

CREATE CONSTRAINT IF NOT EXISTS
  FOR (mi:ManagedIdentity)
  REQUIRE mi.id IS UNIQUE;

CREATE CONSTRAINT IF NOT EXISTS
  FOR (law:LogAnalyticsWorkspace)
  REQUIRE law.id IS UNIQUE;

CREATE CONSTRAINT IF NOT EXISTS
  FOR (s:Subscription)
  REQUIRE s.id IS UNIQUE;

// Composite index for quick lookup of RG + subscription
CREATE INDEX rg_name_sub IF NOT EXISTS
  FOR (rg:ResourceGroup)
  ON (rg.name, rg.subscription_id);
