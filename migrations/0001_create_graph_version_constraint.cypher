// Migration 0001 – create GraphVersion singleton constraint
CREATE CONSTRAINT IF NOT EXISTS
  FOR (v:GraphVersion)
  REQUIRE (v.major, v.minor) IS UNIQUE;
