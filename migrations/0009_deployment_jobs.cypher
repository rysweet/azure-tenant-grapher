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
