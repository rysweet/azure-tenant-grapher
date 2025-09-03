// Migration 0008 - Fix User property names from camelCase to snake_case
// This migration ensures all User nodes have consistent snake_case property names

// First, check and rename userPrincipalName to user_principal_name if it exists
MATCH (u:User)
WHERE u.userPrincipalName IS NOT NULL AND u.user_principal_name IS NULL
SET u.user_principal_name = u.userPrincipalName
REMOVE u.userPrincipalName;

// Rename displayName to display_name if needed
MATCH (u:User)
WHERE u.displayName IS NOT NULL AND u.display_name IS NULL
SET u.display_name = u.displayName
REMOVE u.displayName;

// Rename jobTitle to job_title if needed
MATCH (u:User)
WHERE u.jobTitle IS NOT NULL AND u.job_title IS NULL
SET u.job_title = u.jobTitle
REMOVE u.jobTitle;

// Rename mailNickname to mail_nickname if needed
MATCH (u:User)
WHERE u.mailNickname IS NOT NULL AND u.mail_nickname IS NULL
SET u.mail_nickname = u.mailNickname
REMOVE u.mailNickname;

// Also fix Group nodes if they have similar issues
MATCH (g:Group)
WHERE g.displayName IS NOT NULL AND g.display_name IS NULL
SET g.display_name = g.displayName
REMOVE g.displayName;

// Fix ServicePrincipal nodes
MATCH (sp:ServicePrincipal)
WHERE sp.displayName IS NOT NULL AND sp.display_name IS NULL
SET sp.display_name = sp.displayName
REMOVE sp.displayName;

MATCH (sp:ServicePrincipal)
WHERE sp.appId IS NOT NULL AND sp.app_id IS NULL
SET sp.app_id = sp.appId
REMOVE sp.appId;

// Return count of fixed nodes for verification
MATCH (n)
WHERE n:User OR n:Group OR n:ServicePrincipal
WITH count(n) as totalNodes
RETURN totalNodes as total_identity_nodes;