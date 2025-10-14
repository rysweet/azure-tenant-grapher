// Migration 0009 - Deployment Jobs Tracking Schema
// This migration adds schema for tracking IaC deployment iterations and their relationships

// Create uniqueness constraint on DeploymentJob.job_id
CREATE CONSTRAINT deployment_job_id_unique IF NOT EXISTS
FOR (job:DeploymentJob) REQUIRE job.job_id IS UNIQUE;

// Create index on DeploymentJob.status for filtering
CREATE INDEX deployment_job_status_index IF NOT EXISTS
FOR (job:DeploymentJob) ON (job.status);

// Create index on DeploymentJob.created_at for temporal queries
CREATE INDEX deployment_job_created_at_index IF NOT EXISTS
FOR (job:DeploymentJob) ON (job.created_at);

// Create index on DeploymentJob.tenant_id for filtering by tenant
CREATE INDEX deployment_job_tenant_id_index IF NOT EXISTS
FOR (job:DeploymentJob) ON (job.tenant_id);

// Create composite index for status + tenant filtering
CREATE INDEX deployment_job_status_tenant_index IF NOT EXISTS
FOR (job:DeploymentJob) ON (job.status, job.tenant_id);

// Sample verification queries (commented out - for reference only)

// Query 1: Find all deployment jobs for a specific tenant
// MATCH (job:DeploymentJob {tenant_id: 'example-tenant-id'})
// RETURN job
// ORDER BY job.created_at DESC;

// Query 2: Find the latest deployment job
// MATCH (job:DeploymentJob)
// RETURN job
// ORDER BY job.created_at DESC
// LIMIT 1;

// Query 3: Find deployment iterations chain
// MATCH path = (newer:DeploymentJob)-[:ITERATION_OF*]->(older:DeploymentJob)
// WHERE NOT EXISTS((older)-[:ITERATION_OF]->())
// RETURN path;

// Query 4: Find all resources deployed in a job
// MATCH (job:DeploymentJob)-[:DEPLOYED]->(resource:Resource)
// WHERE job.job_id = 'example-job-id'
// RETURN resource;

// Query 5: Count jobs by status
// MATCH (job:DeploymentJob)
// RETURN job.status, count(*) as count
// ORDER BY count DESC;
