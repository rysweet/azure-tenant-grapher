"""Azure Lighthouse delegation manager for MSSP multi-tenant operations.

This module provides automation for Azure Lighthouse delegation management,
including Bicep template generation, Neo4j tracking, and Azure API integration.

Philosophy:
- Automation-first (no manual portal steps)
- Neo4j as source of truth for delegation state
- Bicep templates for reproducibility
- Fail-fast with clear error messages
- Retry logic for transient Azure API failures

Main Class:
    LighthouseManager: Handles all Lighthouse delegation operations

Example:
    >>> from sentinel.multi_tenant import LighthouseManager
    >>> from azure.identity import DefaultAzureCredential
    >>> from neo4j import GraphDatabase
    >>>
    >>> driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "password"))
    >>> manager = LighthouseManager(
    ...     managing_tenant_id="mssp-tenant-id",
    ...     neo4j_connection=driver,
    ...     bicep_output_dir="./iac_output"
    ... )
    >>>
    >>> # Generate delegation template
    >>> template_path = manager.generate_delegation_template(
    ...     customer_tenant_id="customer-tenant-id",
    ...     customer_tenant_name="Acme Corp",
    ...     subscription_id="subscription-id"
    ... )
"""

import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .exceptions import (
    AzureAPIError,
    DelegationExistsError,
    DelegationNotFoundError,
    InvalidTenantIdError,
    LighthouseError,
    Neo4jQueryError,
)
from .models import LighthouseDelegation, LighthouseStatus

# Optional Azure SDK import (may not be available in test environment)
try:
    from azure.mgmt.managedservices import ManagedServicesClient

    AZURE_SDK_AVAILABLE = True
except ImportError:
    ManagedServicesClient = None  # type: ignore
    AZURE_SDK_AVAILABLE = False

logger = logging.getLogger(__name__)


class LighthouseManager:
    """Manages Azure Lighthouse delegations for MSSP multi-tenant operations.

    This class handles:
    - Bicep template generation with variable substitution
    - Neo4j graph tracking (MSSPTenant, CustomerTenant, LIGHTHOUSE_DELEGATES_TO)
    - Azure Lighthouse API integration for verification and revocation
    - Delegation lifecycle management (pending → active → revoked)

    Attributes:
        managing_tenant_id: MSSP managing tenant ID (UUID)
        bicep_output_dir: Directory for generated Bicep templates
        neo4j_connection: Neo4j driver or session manager
    """

    # Default RBAC authorizations for Sentinel MSSP operations
    DEFAULT_AUTHORIZATIONS = [
        {
            "principalId": "{{PRINCIPAL_ID}}",
            "roleDefinitionId": "ab8e14d6-4a74-4a29-9ba8-549422addade",  # Azure Sentinel Contributor
            "principalIdDisplayName": "Sentinel MSSP Management",
        },
        {
            "principalId": "{{PRINCIPAL_ID}}",
            "roleDefinitionId": "acdd72a7-3385-48ef-bd42-f606fba81ae7",  # Security Reader
            "principalIdDisplayName": "Security Operations Team",
        },
    ]

    def __init__(
        self, managing_tenant_id: str, neo4j_connection: Any, bicep_output_dir: str
    ):
        """Initialize LighthouseManager.

        Args:
            managing_tenant_id: MSSP managing tenant ID (UUID format)
            neo4j_connection: Neo4j driver or session manager
            bicep_output_dir: Directory path for Bicep template output

        Raises:
            InvalidTenantIdError: If managing_tenant_id is not a valid UUID
            ValueError: If bicep_output_dir is invalid
        """
        if not self._is_valid_uuid(managing_tenant_id):
            raise InvalidTenantIdError(managing_tenant_id)

        self.managing_tenant_id = managing_tenant_id
        self.neo4j_connection = neo4j_connection
        self.bicep_output_dir = bicep_output_dir

        # Create output directory if it doesn't exist
        Path(bicep_output_dir).mkdir(parents=True, exist_ok=True)

        # Load Bicep template
        template_path = (
            Path(__file__).parent
            / "bicep_templates"
            / "lighthouse-delegation.bicep.template"
        )
        with open(template_path) as f:
            self.bicep_template = f.read()

        logger.info(
            f"LighthouseManager initialized for managing tenant: {managing_tenant_id}"
        )

    def generate_delegation_template(
        self,
        customer_tenant_id: str,
        customer_tenant_name: str,
        subscription_id: str,
        resource_group: Optional[str] = None,
        authorizations: Optional[List[Dict]] = None,
    ) -> str:
        """Generate Bicep template for Azure Lighthouse delegation.

        This method:
        1. Validates inputs (tenant IDs, subscription ID)
        2. Checks for existing delegation in Neo4j
        3. Substitutes template variables
        4. Writes Bicep file to output directory
        5. Creates Neo4j nodes and relationships (PENDING status)
        6. Generates README with deployment instructions

        Args:
            customer_tenant_id: Customer tenant ID (UUID)
            customer_tenant_name: Human-readable customer name
            subscription_id: Azure subscription ID to delegate (UUID)
            resource_group: Optional resource group name (None = subscription scope)
            authorizations: Optional custom RBAC authorizations (uses defaults if None)

        Returns:
            str: Path to generated Bicep template file

        Raises:
            InvalidTenantIdError: If tenant/subscription IDs are invalid
            DelegationExistsError: If delegation already exists for this customer
            Neo4jQueryError: If Neo4j operations fail
        """
        logger.info(
            f"Generating delegation template for customer: {customer_tenant_name} ({customer_tenant_id})"
        )

        # Validate inputs
        if not self._is_valid_uuid(customer_tenant_id):
            raise InvalidTenantIdError(customer_tenant_id)
        if not self._is_valid_uuid(subscription_id):
            raise LighthouseError(f"Invalid subscription ID format: {subscription_id}")

        # Check for existing delegation
        try:
            existing = self._check_existing_delegation(customer_tenant_id)
            if existing:
                raise DelegationExistsError(
                    customer_tenant_id, existing.get("status", "unknown")
                )
        except (Neo4jQueryError, DelegationExistsError):
            raise
        except Exception as e:
            logger.error(f"Error checking existing delegation: {e}")
            raise Neo4jQueryError("check existing delegation", e) from e

        # Use default authorizations if none provided
        if authorizations is None:
            authorizations = self.DEFAULT_AUTHORIZATIONS

        # Generate template content
        template_content = self._substitute_template_variables(
            customer_tenant_id=customer_tenant_id,
            customer_tenant_name=customer_tenant_name,
            subscription_id=subscription_id,
            resource_group=resource_group,
            authorizations=authorizations,
        )

        # Generate filename (sanitize customer name for filesystem)
        customer_slug = self._slugify(customer_tenant_name)
        timestamp = datetime.now().strftime("%Y%m%d")
        bicep_filename = f"lighthouse-delegation-{customer_slug}-{timestamp}.bicep"
        bicep_path = Path(self.bicep_output_dir) / bicep_filename

        # SECURITY FIX #2: Validate path is within allowed output directory (path traversal protection)
        bicep_path = self._validate_safe_path(bicep_path)

        # Write Bicep template
        bicep_path.write_text(template_content)
        logger.info(f"Generated Bicep template: {bicep_path}")

        # Create Neo4j nodes and relationships
        try:
            self._create_delegation_in_neo4j(
                customer_tenant_id=customer_tenant_id,
                customer_tenant_name=customer_tenant_name,
                subscription_id=subscription_id,
                resource_group=resource_group,
                bicep_template_path=str(bicep_path),
                authorizations=authorizations,
            )
        except Exception as e:
            logger.error(f"Error creating delegation in Neo4j: {e}")
            raise Neo4jQueryError("create delegation", e) from e

        # Generate README
        readme_path = str(bicep_path).replace(".bicep", "-README.md")
        self._generate_readme(
            readme_path=readme_path,
            customer_tenant_name=customer_tenant_name,
            customer_tenant_id=customer_tenant_id,
            subscription_id=subscription_id,
            bicep_filename=bicep_filename,
        )

        return str(bicep_path)

    def register_delegation(
        self,
        customer_tenant_id: str,
        registration_definition_id: str,
        registration_assignment_id: str,
    ) -> LighthouseDelegation:
        """Register delegation after successful Bicep deployment.

        This method updates the Neo4j relationship with Azure resource IDs
        and changes status from PENDING to ACTIVE.

        Args:
            customer_tenant_id: Customer tenant ID (UUID)
            registration_definition_id: Azure registration definition resource ID
            registration_assignment_id: Azure registration assignment resource ID

        Returns:
            LighthouseDelegation: Updated delegation object

        Raises:
            DelegationNotFoundError: If no pending delegation exists
            Neo4jQueryError: If Neo4j operations fail
        """
        logger.info(f"Registering delegation for customer: {customer_tenant_id}")

        # Find pending delegation
        try:
            delegation_data = self._get_delegation_by_tenant_id(customer_tenant_id)
            if not delegation_data:
                raise DelegationNotFoundError(customer_tenant_id)
        except DelegationNotFoundError:
            raise
        except Exception as e:
            raise Neo4jQueryError("find pending delegation", e) from e

        # Update Neo4j with registration IDs
        try:
            self._update_delegation_status(
                customer_tenant_id=customer_tenant_id,
                status=LighthouseStatus.ACTIVE,
                registration_definition_id=registration_definition_id,
                registration_assignment_id=registration_assignment_id,
            )
        except Exception as e:
            raise Neo4jQueryError("update delegation status", e) from e

        # Query updated delegation from Neo4j
        updated_delegation_data = self._get_delegation_by_tenant_id(customer_tenant_id)
        if not updated_delegation_data:
            raise DelegationNotFoundError(customer_tenant_id)
        return self._delegation_from_dict(updated_delegation_data)

    def verify_delegation(self, customer_tenant_id: str, azure_credential: Any) -> bool:
        """Verify delegation status via Azure Lighthouse API.

        This method:
        1. Queries Neo4j for delegation
        2. Calls Azure Managed Services API to verify registration
        3. Updates Neo4j status if verification succeeds/fails

        Args:
            customer_tenant_id: Customer tenant ID (UUID)
            azure_credential: Azure credential object (e.g., DefaultAzureCredential)

        Returns:
            bool: True if delegation is verified active, False otherwise

        Raises:
            Neo4jQueryError: If Neo4j operations fail
        """
        logger.info(f"Verifying delegation for customer: {customer_tenant_id}")

        # Get delegation from Neo4j
        try:
            delegation_data = self._get_delegation_by_tenant_id(customer_tenant_id)
            if not delegation_data:
                logger.warning(
                    f"No delegation found for customer: {customer_tenant_id}"
                )
                return False
        except Exception as e:
            raise Neo4jQueryError("get delegation", e) from e

        registration_assignment_id = delegation_data.get("registration_assignment_id")
        if not registration_assignment_id:
            logger.warning(
                f"Delegation has no registration assignment ID (status: {delegation_data.get('status')})"
            )
            return False

        # Call Azure Lighthouse API
        try:
            if not AZURE_SDK_AVAILABLE or ManagedServicesClient is None:
                logger.warning("Azure SDK not available - cannot verify delegation")
                return False

            client = ManagedServicesClient(
                credential=azure_credential,
                subscription_id=delegation_data["subscription_id"],
            )

            # Extract assignment name from resource ID
            assignment_name = registration_assignment_id.split("/")[-1]

            # SECURITY FIX #4: Get registration assignment with retry logic
            assignment = self._retry_with_backoff(
                operation_name="verify_delegation",
                func=lambda: client.registration_assignments.get(
                    scope=f"/subscriptions/{delegation_data['subscription_id']}",
                    registration_assignment_id=assignment_name,
                ),
            )

            if assignment:
                logger.info(f"Delegation verified active: {customer_tenant_id}")
                # Update status to ACTIVE
                self._update_delegation_status(
                    customer_tenant_id=customer_tenant_id,
                    status=LighthouseStatus.ACTIVE,
                )
                return True
            else:
                logger.warning(f"Delegation not found in Azure: {customer_tenant_id}")
                return False

        except Exception as e:
            logger.error(f"Azure API error during verification: {e}")
            # Update status to ERROR
            try:
                self._update_delegation_status(
                    customer_tenant_id=customer_tenant_id,
                    status=LighthouseStatus.ERROR,
                    error_message=str(e),
                )
            except Exception as neo4j_error:
                # SECURITY FIX: Don't swallow exceptions silently - log the error
                logger.error(
                    f"Failed to update delegation status to ERROR in Neo4j: {neo4j_error}"
                )
            return False

    def list_delegations(
        self, status_filter: Optional[LighthouseStatus] = None
    ) -> List[LighthouseDelegation]:
        """List all Lighthouse delegations from Neo4j.

        Args:
            status_filter: Optional filter by delegation status (None = all)

        Returns:
            List[LighthouseDelegation]: List of delegation objects

        Raises:
            Neo4jQueryError: If Neo4j query fails
        """
        logger.info(
            f"Listing delegations (filter: {status_filter.value if status_filter else 'all'})"
        )

        try:
            delegations_data = self._query_delegations(status_filter=status_filter)
            return [self._delegation_from_dict(d) for d in delegations_data]
        except Exception as e:
            raise Neo4jQueryError("list delegations", e) from e

    def revoke_delegation(self, customer_tenant_id: str, azure_credential: Any) -> None:
        """Revoke Azure Lighthouse delegation.

        This method:
        1. Queries Neo4j for delegation
        2. Calls Azure API to delete registration assignment
        3. Updates Neo4j status to REVOKED

        Args:
            customer_tenant_id: Customer tenant ID (UUID)
            azure_credential: Azure credential object

        Raises:
            DelegationNotFoundError: If delegation doesn't exist
            AzureAPIError: If Azure API call fails
            Neo4jQueryError: If Neo4j operations fail
        """
        logger.info(f"Revoking delegation for customer: {customer_tenant_id}")

        # Get delegation
        delegation_data = self._get_delegation_by_tenant_id(customer_tenant_id)
        if not delegation_data:
            raise DelegationNotFoundError(customer_tenant_id)

        registration_assignment_id = delegation_data.get("registration_assignment_id")
        if not registration_assignment_id:
            logger.warning(
                "Delegation has no registration assignment ID - marking as revoked in Neo4j"
            )
        else:
            # Call Azure API to delete
            try:
                if not AZURE_SDK_AVAILABLE or ManagedServicesClient is None:
                    logger.warning(
                        "Azure SDK not available - skipping Azure API deletion"
                    )
                else:
                    client = ManagedServicesClient(
                        credential=azure_credential,
                        subscription_id=delegation_data["subscription_id"],
                    )

                    assignment_name = registration_assignment_id.split("/")[-1]

                    # SECURITY FIX #4: Delete with retry logic
                    self._retry_with_backoff(
                        operation_name="revoke_delegation",
                        func=lambda: client.registration_assignments.delete(
                            scope=f"/subscriptions/{delegation_data['subscription_id']}",
                            registration_assignment_id=assignment_name,
                        ),
                    )
                    logger.info(
                        f"Deleted Azure Lighthouse registration assignment: {assignment_name}"
                    )

            except Exception as e:
                logger.error(f"Azure API error during revocation: {e}")
                raise AzureAPIError("revoke delegation", e) from e

        # Update Neo4j status
        try:
            self._update_delegation_status(
                customer_tenant_id=customer_tenant_id, status=LighthouseStatus.REVOKED
            )
        except Exception as e:
            raise Neo4jQueryError("update delegation status to revoked", e) from e

        logger.info(f"Delegation revoked successfully: {customer_tenant_id}")

    # ============================================================================
    # Private Helper Methods
    # ============================================================================

    @staticmethod
    def _is_valid_uuid(value: str) -> bool:
        """Validate UUID format (8-4-4-4-12)."""
        if not value or not isinstance(value, str):
            return False
        uuid_pattern = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
        return bool(re.match(uuid_pattern, value))

    @staticmethod
    def _slugify(text: str) -> str:
        """Convert text to filesystem-safe slug."""
        text = text.lower()
        text = re.sub(r"[^a-z0-9-]", "-", text)
        text = re.sub(r"-+", "-", text)
        return text.strip("-")

    @staticmethod
    def _sanitize_for_bicep(text: str, max_length: int = 100) -> str:
        """Sanitize user input for safe Bicep template substitution.

        SECURITY: Prevents template injection attacks by validating and escaping
        user-provided strings before inserting them into Bicep templates.

        Args:
            text: User-provided string (e.g., customer name)
            max_length: Maximum allowed length (default: 100)

        Returns:
            str: Sanitized string safe for Bicep templates

        Raises:
            LighthouseError: If input contains invalid characters or is too long
        """
        if not text or not isinstance(text, str):
            raise LighthouseError("Input must be a non-empty string")

        if len(text) > max_length:
            raise LighthouseError(
                f"Input exceeds maximum length of {max_length} characters"
            )

        # Allow only alphanumeric, spaces (not newlines!), and common business name characters
        # Pattern: letters, numbers, spaces, hyphens, underscores, periods, parentheses, ampersands
        # Note: \s includes newlines/tabs, so we use explicit space character instead
        safe_pattern = r"^[a-zA-Z0-9 \-_.()&]+$"
        if not re.match(safe_pattern, text):
            raise LighthouseError(
                "Input contains invalid characters. Allowed: letters, numbers, spaces, -_.()&"
            )

        # Escape any Bicep-specific characters (though pattern should prevent them)
        # Bicep uses ${} for expressions, so escape $ if it somehow got through
        text = text.replace("$", "\\$")
        text = text.replace("{", "\\{")
        text = text.replace("}", "\\}")

        return text

    def _validate_safe_path(self, file_path: Path) -> Path:
        """Validate that a file path is within the allowed output directory.

        SECURITY: Prevents path traversal attacks by ensuring generated files
        stay within the configured bicep_output_dir.

        Args:
            file_path: Path to validate

        Returns:
            Path: Resolved absolute path if safe

        Raises:
            LighthouseError: If path escapes the output directory
        """
        try:
            # Resolve both paths to absolute paths (follows symlinks)
            output_dir_resolved = Path(self.bicep_output_dir).resolve()
            file_path_resolved = file_path.resolve()

            # Check if file_path is within output_dir
            # relative_to() will raise ValueError if file_path is outside output_dir
            file_path_resolved.relative_to(output_dir_resolved)

            return file_path_resolved

        except ValueError as e:
            raise LighthouseError(
                f"Security violation: Path '{file_path}' is outside allowed directory '{self.bicep_output_dir}'"
            ) from e

    def _retry_with_backoff(
        self,
        operation_name: str,
        func: callable,
        max_retries: int = 3,
        initial_delay: float = 1.0,
    ) -> Any:
        """Execute Azure API call with exponential backoff retry logic.

        SECURITY: Implements rate limiting protection and graceful handling of
        transient Azure API errors (429, 503, network timeouts).

        Args:
            operation_name: Human-readable name for logging
            func: Callable to execute (Azure SDK call)
            max_retries: Maximum retry attempts (default: 3)
            initial_delay: Initial delay in seconds (default: 1.0)

        Returns:
            Any: Result from successful function call

        Raises:
            AzureAPIError: If all retries are exhausted
        """
        last_exception = None

        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                last_exception = e
                error_str = str(e).lower()

                # Check if error is retryable (rate limiting, timeouts, service unavailable)
                is_retryable = any(
                    x in error_str
                    for x in ["429", "503", "timeout", "throttle", "rate limit"]
                )

                if not is_retryable or attempt == max_retries - 1:
                    # Not retryable or final attempt - raise immediately
                    raise AzureAPIError(operation_name, e) from e

                # Calculate exponential backoff delay
                delay = initial_delay * (2**attempt)
                logger.warning(
                    f"Azure API {operation_name} failed (attempt {attempt + 1}/{max_retries}): {e}. "
                    f"Retrying in {delay:.1f}s..."
                )
                time.sleep(delay)

        # Should never reach here, but for safety
        raise AzureAPIError(operation_name, last_exception) from last_exception

    def _substitute_template_variables(
        self,
        customer_tenant_id: str,
        customer_tenant_name: str,
        subscription_id: str,
        resource_group: Optional[str],
        authorizations: List[Dict],
    ) -> str:
        """Substitute variables in Bicep template.

        SECURITY: All user-provided inputs are sanitized before template substitution
        to prevent template injection attacks.
        """
        content = self.bicep_template

        # SECURITY FIX #1: Sanitize customer name before template substitution
        sanitized_customer_name = self._sanitize_for_bicep(customer_tenant_name)

        # If resource group is specified, change scope to 'resourceGroup'
        if resource_group:
            # SECURITY FIX #1: Sanitize resource group name
            self._sanitize_for_bicep(resource_group)
            content = content.replace(
                "targetScope = 'subscription'", "targetScope = 'resourceGroup'"
            )
        else:
            pass

        content = content.replace("{{MANAGING_TENANT_ID}}", self.managing_tenant_id)
        content = content.replace("{{CUSTOMER_NAME}}", sanitized_customer_name)
        content = content.replace("{{CUSTOMER_TENANT_ID}}", customer_tenant_id)
        content = content.replace("{{SUBSCRIPTION_ID}}", subscription_id)
        content = content.replace(
            "{{AUTHORIZATIONS_JSON}}", json.dumps(authorizations, indent=2)
        )
        return content

    def _check_existing_delegation(self, customer_tenant_id: str) -> Optional[Dict]:
        """Check if delegation already exists in Neo4j.

        SECURITY NOTE (Cypher Injection): This code is SAFE because it uses Neo4j
        parameterized queries ($managing_tenant_id, $customer_tenant_id). Parameters
        are passed separately to tx.run() and are automatically escaped by the Neo4j driver.

        ⚠️ WARNING: NEVER use string interpolation/f-strings to build Cypher queries!
        ❌ BAD:  query = f"MATCH (t {{tenant_id: '{tenant_id}'}}) RETURN t"
        ✅ GOOD: query = "MATCH (t {tenant_id: $tenant_id}) RETURN t"
                 tx.run(query, tenant_id=tenant_id)
        """
        query = """
        MATCH (m:MSSPTenant {tenant_id: $managing_tenant_id})-[r:LIGHTHOUSE_DELEGATES_TO]->(c:CustomerTenant {tenant_id: $customer_tenant_id})
        RETURN r.status as status
        """
        with self.neo4j_connection.session() as session:
            with session.begin_transaction() as tx:
                result = tx.run(
                    query,
                    managing_tenant_id=self.managing_tenant_id,
                    customer_tenant_id=customer_tenant_id,
                )
                record = result.single()
                return dict(record) if record else None

    def _create_delegation_in_neo4j(
        self,
        customer_tenant_id: str,
        customer_tenant_name: str,
        subscription_id: str,
        resource_group: Optional[str],
        bicep_template_path: str,
        authorizations: List[Dict],
    ) -> None:
        """Create Neo4j nodes and relationships for delegation."""
        query = """
        // Create or update MSSPTenant node
        MERGE (m:MSSPTenant {tenant_id: $managing_tenant_id})
        ON CREATE SET m.created_at = datetime(), m.updated_at = datetime()
        ON MATCH SET m.updated_at = datetime()

        // Create CustomerTenant node
        MERGE (c:CustomerTenant {tenant_id: $customer_tenant_id})
        ON CREATE SET
            c.tenant_name = $customer_tenant_name,
            c.created_at = datetime(),
            c.updated_at = datetime()
        ON MATCH SET
            c.tenant_name = $customer_tenant_name,
            c.updated_at = datetime()

        // Create LIGHTHOUSE_DELEGATES_TO relationship
        MERGE (m)-[r:LIGHTHOUSE_DELEGATES_TO]->(c)
        ON CREATE SET
            r.subscription_id = $subscription_id,
            r.resource_group = $resource_group,
            r.status = $status,
            r.bicep_template_path = $bicep_template_path,
            r.authorizations = $authorizations,
            r.created_at = datetime(),
            r.updated_at = datetime()
        ON MATCH SET
            r.subscription_id = $subscription_id,
            r.resource_group = $resource_group,
            r.status = $status,
            r.bicep_template_path = $bicep_template_path,
            r.authorizations = $authorizations,
            r.updated_at = datetime()

        RETURN c
        """
        with self.neo4j_connection.session() as session:
            with session.begin_transaction() as tx:
                tx.run(
                    query,
                    managing_tenant_id=self.managing_tenant_id,
                    customer_tenant_id=customer_tenant_id,
                    customer_tenant_name=customer_tenant_name,
                    subscription_id=subscription_id,
                    resource_group=resource_group,
                    status=LighthouseStatus.PENDING.value,
                    bicep_template_path=bicep_template_path,
                    authorizations=json.dumps(authorizations),
                )
                tx.commit()

    def _get_delegation_by_tenant_id(self, customer_tenant_id: str) -> Optional[Dict]:
        """Get delegation from Neo4j by customer tenant ID."""
        query = """
        MATCH (m:MSSPTenant {tenant_id: $managing_tenant_id})-[r:LIGHTHOUSE_DELEGATES_TO]->(c:CustomerTenant {tenant_id: $customer_tenant_id})
        RETURN
            c.tenant_id as customer_tenant_id,
            c.tenant_name as customer_tenant_name,
            m.tenant_id as managing_tenant_id,
            r.subscription_id as subscription_id,
            r.resource_group as resource_group,
            r.status as status,
            r.registration_definition_id as registration_definition_id,
            r.registration_assignment_id as registration_assignment_id,
            r.bicep_template_path as bicep_template_path,
            r.authorizations as authorizations,
            r.error_message as error_message,
            r.created_at as created_at,
            r.updated_at as updated_at
        """
        with self.neo4j_connection.session() as session:
            with session.begin_transaction() as tx:
                result = tx.run(
                    query,
                    managing_tenant_id=self.managing_tenant_id,
                    customer_tenant_id=customer_tenant_id,
                )
                record = result.single()
                return dict(record) if record else None

    def _update_delegation_status(
        self,
        customer_tenant_id: str,
        status: LighthouseStatus,
        registration_definition_id: Optional[str] = None,
        registration_assignment_id: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """Update delegation status in Neo4j."""
        query = """
        MATCH (m:MSSPTenant {tenant_id: $managing_tenant_id})-[r:LIGHTHOUSE_DELEGATES_TO]->(c:CustomerTenant {tenant_id: $customer_tenant_id})
        SET r.status = $status,
            r.updated_at = datetime()
        """

        params = {
            "managing_tenant_id": self.managing_tenant_id,
            "customer_tenant_id": customer_tenant_id,
            "status": status.value,
        }

        if registration_definition_id:
            query += ", r.registration_definition_id = $registration_definition_id"
            params["registration_definition_id"] = registration_definition_id

        if registration_assignment_id:
            query += ", r.registration_assignment_id = $registration_assignment_id"
            params["registration_assignment_id"] = registration_assignment_id

        if error_message:
            query += ", r.error_message = $error_message"
            params["error_message"] = error_message

        with self.neo4j_connection.session() as session:
            with session.begin_transaction() as tx:
                tx.run(query, **params)
                tx.commit()

    def _query_delegations(
        self, status_filter: Optional[LighthouseStatus] = None
    ) -> List[Dict]:
        """Query all delegations from Neo4j."""
        query = """
        MATCH (m:MSSPTenant {tenant_id: $managing_tenant_id})-[r:LIGHTHOUSE_DELEGATES_TO]->(c:CustomerTenant)
        """

        if status_filter:
            query += " WHERE r.status = $status"

        query += """
        RETURN
            c.tenant_id as customer_tenant_id,
            c.tenant_name as customer_tenant_name,
            m.tenant_id as managing_tenant_id,
            r.subscription_id as subscription_id,
            r.resource_group as resource_group,
            r.status as status,
            r.registration_definition_id as registration_definition_id,
            r.registration_assignment_id as registration_assignment_id,
            r.bicep_template_path as bicep_template_path,
            r.authorizations as authorizations,
            r.error_message as error_message,
            r.created_at as created_at,
            r.updated_at as updated_at
        """

        params = {"managing_tenant_id": self.managing_tenant_id}
        if status_filter:
            params["status"] = status_filter.value

        with self.neo4j_connection.session() as session:
            with session.begin_transaction() as tx:
                result = tx.run(query, **params)
                return result.data()

    def _delegation_from_dict(self, data: Dict) -> LighthouseDelegation:
        """Create LighthouseDelegation from Neo4j result dict."""
        # Parse authorizations JSON if it's a string
        authorizations = data.get("authorizations")
        if isinstance(authorizations, str):
            authorizations = json.loads(authorizations)

        return LighthouseDelegation(
            customer_tenant_id=data["customer_tenant_id"],
            customer_tenant_name=data["customer_tenant_name"],
            managing_tenant_id=data["managing_tenant_id"],
            subscription_id=data["subscription_id"],
            resource_group=data.get("resource_group"),
            registration_definition_id=data.get("registration_definition_id"),
            registration_assignment_id=data.get("registration_assignment_id"),
            status=LighthouseStatus(data["status"]),
            created_at=data.get("created_at", datetime.now()),
            updated_at=data.get("updated_at", datetime.now()),
            bicep_template_path=data["bicep_template_path"],
            authorizations=authorizations,
            error_message=data.get("error_message"),
        )

    def _generate_readme(
        self,
        readme_path: str,
        customer_tenant_name: str,
        customer_tenant_id: str,
        subscription_id: str,
        bicep_filename: str,
    ) -> None:
        """Generate README with deployment instructions."""
        content = f"""# Azure Lighthouse Delegation - {customer_tenant_name}

This directory contains the Azure Lighthouse delegation template for **{customer_tenant_name}**.

## Delegation Details

- **Customer Tenant ID**: `{customer_tenant_id}`
- **Managing Tenant ID**: `{self.managing_tenant_id}`
- **Subscription ID**: `{subscription_id}`
- **Generated**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Deployment Instructions

### Prerequisites

1. Azure CLI installed and authenticated
2. User must have Owner or User Access Administrator role on the subscription
3. Customer tenant must register `Microsoft.ManagedServices` resource provider

### Deploy Delegation

```bash
# 1. Login to customer tenant
az login --tenant {customer_tenant_id}

# 2. Set subscription context
az account set --subscription {subscription_id}

# 3. Register resource provider (if not already registered)
az provider register --namespace Microsoft.ManagedServices

# 4. Deploy Bicep template
az deployment sub create \\
    --location eastus \\
    --template-file {bicep_filename} \\
    --name lighthouse-delegation-{self._slugify(customer_tenant_name)}

# 5. Verify deployment
az managedservices assignment list --output table
```

### Verify Delegation

After deployment, verify the delegation is active:

```bash
# List delegations
az managedservices assignment list

# Get delegation details
az managedservices definition show \\
    --name <registration-definition-name>
```

### Revoke Delegation

To revoke this delegation:

```bash
# Using Azure CLI
az managedservices assignment delete \\
    --name <registration-assignment-name>

# OR using ATG CLI
atg lighthouse revoke --customer-tenant {customer_tenant_id}
```

## Support

For issues or questions, contact your MSSP security operations team.
"""
        Path(readme_path).write_text(content)
        logger.info(f"Generated README: {readme_path}")
