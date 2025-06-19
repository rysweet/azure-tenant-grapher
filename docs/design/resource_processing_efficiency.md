# Resource Processing Efficiency Improvement

## Context
The Azure Tenant Grapher currently shows a very high **Skipped** count when starting from
an empty graph. Investigation shows duplicate resource IDs and intra-run race conditions
cause resources to be mistakenly classified as “already processed”.

## Root cause summary
1. Duplicate resource IDs returned by Azure REST paging.  
2. Concurrent worker threads querying Neo4j before the first insert commits.  
3. Skip logic that treats “node exists” as “fully processed”.

## Objectives
- Each logical resource processed exactly **once** per build.  
- Reduce redundant Neo4j reads / writes.  
- Retain existing `max_concurrency` throughput.  
- Preserve resume-ability across separate runs.

## Proposed technical changes

1. **Pre-run in-memory de-duplication**

   ```python
   id_map: dict[str, dict[str, Any]] = {}
   for r in all_resources:
       rid = r.get("id")
       if rid:
           id_map[rid] = r           # keep last occurrence
   all_resources = list(id_map.values())
   logger.info("🗂️  De-duplicated list → %d unique IDs", len(all_resources))
   ```
   Expected: eliminates API duplicates and guarantees ≤ 1 task per ID.

2. **Thread-safe `seen` guard**

   ```python
   self._seen_ids: set[str] = set()
   self._seen_lock = threading.Lock()

   with self._seen_lock:
       if rid in self._seen_ids:
           self.stats.skipped += 1          # intra-run duplicate
           return True
       self._seen_ids.add(rid)
   ```
   Prevents race where a second thread handles the same ID in the same run.

3. **Unified skip Cypher query**

   Replace `resource_exists` + `has_llm_description` with:

   ```cypher
   MATCH (r:Resource {id:$id})
   RETURN (r.processing_status = 'completed')        AS done,
          r.llm_description IS NOT NULL
          AND NOT r.llm_description STARTS WITH 'Azure ' AS good_desc
   ```
   Skip only when `done AND good_desc`.

4. **Mark `processing_status='processing'` earlier**

   Ensure the first `MERGE` sets status before lengthy LLM work,
   so competing threads can detect `in_progress` and skip gracefully.

5. **Optional batch upserts**

   Collect N resources and flush via one `UNWIND $batch` each second.
   Shrinks write latency and race window.

## Roll-out plan
1. **Phase 1 (quick win)** – implement items 1-2, add unit tests; target 1 day.  
2. **Phase 2** – implement unified Cypher skip; update skip-count tests.  
3. **Phase 3** – implement items 4-5 for maximum throughput.

## Acceptance criteria
- **Skipped** count < 5 % on fresh-DB runs.  
- Build runtime improves by ≥ 30 % on a 1 k-resource tenant.

## Risks
- Additional memory for the de-duplication map / `seen` set.  
- Minor lock contention in `seen` guard (bounded by number of dup IDs).

## Tracking
This document tracks design and implementation tasks; update as PRs land.