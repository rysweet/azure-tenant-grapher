/*
Migration: Add uniqueness constraints for DiagnosticSetting and AlertRule nodes
Issue: #58 (Operational Instrumentation Nodes)
*/

CREATE CONSTRAINT IF NOT EXISTS
  FOR (ds:DiagnosticSetting)
  REQUIRE ds.id IS UNIQUE;

CREATE CONSTRAINT IF NOT EXISTS
  FOR (ar:AlertRule)
  REQUIRE ar.id IS UNIQUE;
