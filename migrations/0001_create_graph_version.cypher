// Migration 0001 – create GraphVersion singleton & uniqueness
CREATE CONSTRAINT IF NOT EXISTS
  FOR (v:GraphVersion)
  REQUIRE (v.major, v.minor) IS UNIQUE;

MERGE (v:GraphVersion {major:1, minor:0})
  ON CREATE
    SET v.appliedAt = datetime();
