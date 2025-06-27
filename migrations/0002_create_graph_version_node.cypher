// Migration 0002 – create initial GraphVersion node
MERGE (v:GraphVersion {major:1, minor:0})
  ON CREATE
    SET v.appliedAt = datetime();
