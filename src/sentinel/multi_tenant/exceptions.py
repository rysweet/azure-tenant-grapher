"""Custom exceptions for Azure Lighthouse operations.

Philosophy:
- Clear exception hierarchy
- Specific error types for different failure modes
- Helpful error messages
- No generic exceptions

Exception Hierarchy:
    LighthouseError (base)
    ├── DelegationNotFoundError
    ├── DelegationExistsError
    └── (other specific errors inherit from base)
"""


class LighthouseError(Exception):
    """Base exception for all Azure Lighthouse operations.

    All Lighthouse-specific exceptions inherit from this base class,
    making it easy to catch all Lighthouse-related errors.

    Example:
        >>> try:
        ...     manager.generate_delegation_template(...)
        ... except LighthouseError as e:
        ...     print(f"Lighthouse operation failed: {e}")
    """

    pass


class DelegationNotFoundError(LighthouseError):
    """Raised when a delegation is not found in Neo4j or Azure.

    This error occurs when attempting to operate on a delegation that
    doesn't exist (e.g., verify, revoke, or update a non-existent delegation).

    Example:
        >>> manager.revoke_delegation(customer_tenant_id="non-existent-id")
        DelegationNotFoundError: No delegation found for customer tenant: non-existent-id
    """

    def __init__(self, customer_tenant_id: str):
        self.customer_tenant_id = customer_tenant_id
        super().__init__(
            f"No delegation found for customer tenant: {customer_tenant_id}"
        )


class DelegationExistsError(LighthouseError):
    """Raised when attempting to create a delegation that already exists.

    This error prevents accidentally creating duplicate delegations for
    the same customer tenant.

    Example:
        >>> manager.generate_delegation_template(customer_tenant_id="existing-id", ...)
        DelegationExistsError: Delegation already exists for customer tenant: existing-id (status: active)
    """

    def __init__(self, customer_tenant_id: str, status: str):
        self.customer_tenant_id = customer_tenant_id
        self.status = status
        super().__init__(
            f"Delegation already exists for customer tenant: {customer_tenant_id} "
            f"(status: {status})"
        )


class AzureAPIError(LighthouseError):
    """Raised when Azure API calls fail.

    This wraps Azure SDK exceptions with additional context about
    the Lighthouse operation that failed.

    Attributes:
        operation: Name of the operation that failed
        azure_error: Original Azure SDK exception
    """

    def __init__(self, operation: str, azure_error: Exception):
        self.operation = operation
        self.azure_error = azure_error
        super().__init__(f"Azure API call failed during {operation}: {azure_error!s}")


class Neo4jQueryError(LighthouseError):
    """Raised when Neo4j database operations fail.

    This wraps Neo4j driver exceptions with additional context about
    the query that failed.

    Attributes:
        query_description: Description of the query that failed
        neo4j_error: Original Neo4j driver exception
    """

    def __init__(self, query_description: str, neo4j_error: Exception):
        self.query_description = query_description
        self.neo4j_error = neo4j_error
        super().__init__(f"Neo4j query failed ({query_description}): {neo4j_error!s}")


class InvalidTenantIdError(LighthouseError):
    """Raised when a tenant ID is not a valid UUID format.

    Tenant IDs must follow the UUID format: 8-4-4-4-12 hex digits.

    Example:
        >>> manager.generate_delegation_template(customer_tenant_id="invalid", ...)
        InvalidTenantIdError: Invalid tenant ID format: invalid (expected UUID format)
    """

    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        super().__init__(
            f"Invalid tenant ID format: {tenant_id} (expected UUID format: "
            f"xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)"
        )
