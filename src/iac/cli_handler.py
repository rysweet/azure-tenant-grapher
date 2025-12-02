"""CLI handler for Infrastructure-as-Code generation commands.

This module provides the command handler for IaC generation functionality
in the Azure Tenant Grapher CLI.
"""

import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

import click
from neo4j import Driver  # type: ignore

from ..config_manager import create_neo4j_config_from_env
from ..deployment_registry import DeploymentRegistry
from ..utils.session_manager import create_session_manager
from .auto_identity_mapper import AutoIdentityMapper
from .emitters import get_emitter
from .engine import TransformationEngine
from .generation_report import GenerationMetrics, GenerationReport, UnsupportedTypeInfo
from .subset import SubsetFilter
from .traverser import GraphTraverser

logger = logging.getLogger(__name__)


def validate_output_path(user_path: str, base_dir: Path = Path("outputs")) -> Path:
    """
    Validate and sanitize output path to prevent path traversal attacks.

    Ensures the requested path is within the allowed base directory.

    Args:
        user_path: User-supplied output path
        base_dir: Base directory for outputs (default: "outputs")

    Returns:
        Validated absolute path within base directory

    Raises:
        ValueError: If path attempts to traverse outside base directory

    Example:
        >>> validate_output_path("my-output", Path("outputs"))
        PosixPath('/home/user/project/outputs/my-output')
        >>> validate_output_path("../../etc/passwd", Path("outputs"))
        ValueError: Output path must be within outputs...
    """
    # Resolve to absolute paths to detect traversal
    requested_path = Path(user_path).resolve()
    base_path = base_dir.resolve()

    # Ensure requested path is within base directory
    try:
        # relative_to() will raise ValueError if not a subpath
        requested_path.relative_to(base_path)
    except ValueError:
        raise ValueError(
            f"Output path must be within {base_dir}. "
            f"Requested path '{user_path}' resolves to '{requested_path}' "
            f"which is outside allowed base directory '{base_path}'"
        )

    return requested_path


def get_neo4j_driver_from_config() -> Driver:
    """Get Neo4j driver from configuration."""
    config = create_neo4j_config_from_env()
    manager = create_session_manager(config.neo4j)
    manager.connect()
    # pyright: ignore[reportPrivateUsage]
    if manager._driver is None:  # pyright: ignore[reportPrivateUsage]
        raise RuntimeError("Neo4j driver is not initialized")
    return manager._driver  # pyright: ignore[reportPrivateUsage]  # Driver object (protected access intentional)


def default_timestamped_dir() -> Path:
    """Create default timestamped output directory inside outputs/."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    outdir = Path("outputs") / f"iac-out-{timestamp}"
    outdir.mkdir(parents=True, exist_ok=True)
    return outdir


def _get_default_subscription_from_azure_cli() -> Optional[tuple[str, str]]:
    """Get default subscription ID and tenant ID from Azure CLI.

    Returns:
        Tuple of (subscription_id, tenant_id) or None if not available.
    """
    try:
        result = subprocess.run(
            [
                "az",
                "account",
                "show",
                "--query",
                "{subscriptionId:id, tenantId:tenantId}",
                "-o",
                "json",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            subscription_id = data.get("subscriptionId")
            tenant_id = data.get("tenantId")
            if subscription_id and tenant_id:
                logger.debug(
                    f"Retrieved from Azure CLI: subscription={subscription_id}, tenant={tenant_id}"
                )
                return (subscription_id, tenant_id)
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError) as e:
        logger.debug(f"Could not retrieve subscription/tenant from Azure CLI: {e}")
    return None


async def _handle_terraform_import(
    subscription_id: str,
    terraform_dir: Path,
    import_strategy_str: str,
) -> None:
    """Handle Terraform import of pre-existing resources.

    This function integrates TerraformImporter into the IaC generation workflow.
    It's non-blocking - if import fails, we log the error and continue.

    Args:
        subscription_id: Target Azure subscription ID
        terraform_dir: Directory containing generated Terraform files
        import_strategy_str: Strategy string from CLI (resource_groups, all_resources, selective)

    Raises:
        Does not raise - errors are logged and reported but don't block IaC generation
    """
    import shutil

    import click

    from .importers.terraform_importer import ImportStrategy, TerraformImporter

    try:
        # Check if terraform is installed
        if not shutil.which("terraform"):
            logger.warning(
                "Terraform not found in PATH - skipping import. "
                "Install Terraform to enable auto-import functionality."
            )
            click.echo(
                "⚠️  Warning: Terraform not found in PATH. "
                "Skipping import of pre-existing resources."
            )
            return

        # Convert strategy string to enum
        strategy_map = {
            "resource_groups": ImportStrategy.RESOURCE_GROUPS,
            "all_resources": ImportStrategy.ALL_RESOURCES,
            "selective": ImportStrategy.SELECTIVE,
        }
        strategy = strategy_map.get(
            import_strategy_str.lower(), ImportStrategy.RESOURCE_GROUPS
        )

        logger.info(
            f"Starting Terraform import with strategy: {strategy.value} (Issue #412)"
        )
        click.echo(f"\n🔄 Importing pre-existing Azure resources ({strategy.value})...")

        # Initialize importer
        importer = TerraformImporter(
            subscription_id=subscription_id,
            terraform_dir=str(terraform_dir),
            import_strategy=strategy,
            dry_run=False,
        )

        # Run import workflow
        report = await importer.run_import()

        # Display report
        click.echo("\n" + report.format_report())

        # Log summary
        if report.successes > 0:
            logger.info(
                f"Successfully imported {report.successes} resources into Terraform state"
            )
        if report.failures > 0:
            logger.warning(
                f"Failed to import {report.failures} resources. Check report for details."
            )

    except Exception as e:
        # Non-blocking error - log and continue
        logger.error(f"Terraform import failed: {e}", exc_info=True)
        click.echo(
            f"⚠️  Warning: Terraform import failed: {e}. "
            f"IaC generation completed, but resources may need manual import.",
            err=True,
        )


async def generate_iac_command_handler(
    tenant_id: Optional[str] = None,
    format_type: str = "terraform",
    output_path: Optional[str] = None,
    rules_file: Optional[str] = None,
    dry_run: bool = False,
    resource_filters: Optional[str] = None,
    subset_filter: Optional[str] = None,
    node_ids: Optional[list[str]] = None,
    dest_rg: Optional[str] = None,
    location: Optional[str] = None,
    skip_validation: bool = False,
    skip_subnet_validation: bool = False,
    auto_fix_subnets: bool = False,
    preserve_rg_structure: bool = False,
    domain_name: Optional[str] = None,
    naming_suffix: Optional[str] = None,
    skip_name_validation: bool = False,
    skip_address_space_validation: bool = False,
    auto_renumber_address_spaces: bool = False,
    preserve_names: bool = False,
    auto_purge_soft_deleted: bool = False,
    # Conflict detection parameters (Issue #336)
    check_conflicts: bool = True,
    skip_conflict_check: bool = False,
    auto_cleanup: bool = False,
    fail_on_conflicts: bool = True,
    resource_group_prefix: Optional[str] = None,
    target_subscription: Optional[str] = None,
    # Cross-tenant translation parameters (Issue #406)
    source_tenant_id: Optional[str] = None,
    target_tenant_id: Optional[str] = None,
    identity_mapping_file: Optional[str] = None,
    strict_translation: bool = False,
    # Terraform import parameters (Issue #412)
    auto_import_existing: bool = False,
    import_strategy: str = "resource_groups",
    # Provider registration parameters
    auto_register_providers: bool = False,
    # Smart import parameters (Phase 1F)
    scan_target: bool = False,
    scan_target_tenant_id: Optional[str] = None,
    scan_target_subscription_id: Optional[str] = None,
    # Community splitting parameters
    split_by_community: bool = False,
) -> int:
    """Handle the generate-iac CLI command.

    Args:
        tenant_id: Azure tenant ID to process
        format_type: Target IaC format (terraform, arm, bicep)
        output_path: Output directory for generated templates
        rules_file: Path to transformation rules configuration file
        dry_run: If True, only validate inputs without generating templates
        resource_filters: Optional resource type filters
        subset_filter: Optional subset filter string
        node_ids: Optional list of specific node IDs to generate IaC for
        dest_rg: Target resource group name for Bicep module deployment
        location: Target location/region for resource deployment
        skip_validation: Skip Terraform validation after generation
        skip_subnet_validation: Skip subnet containment validation (Issue #333)
        auto_fix_subnets: Auto-fix subnet addresses outside VNet range (Issue #333)
        preserve_rg_structure: Preserve source resource group structure in target deployment
        domain_name: Domain name for entities that require one
        naming_suffix: Optional custom naming suffix for conflict resolution
        skip_name_validation: Skip global name conflict validation
        skip_address_space_validation: Skip VNet address space validation (GAP-012)
        auto_renumber_address_spaces: Auto-renumber conflicting VNet address spaces (GAP-012)
        preserve_names: Preserve original resource names; fail on conflicts (GAP-015)
        auto_purge_soft_deleted: Auto-purge soft-deleted Key Vaults (GAP-016)
        check_conflicts: Enable pre-deployment conflict detection (default: True)
        skip_conflict_check: Skip conflict detection (default: False)
        target_subscription: Target Azure subscription ID (overrides auto-detection from resources)
        auto_cleanup: Automatically run cleanup script on conflicts (default: False)
        fail_on_conflicts: Fail deployment if conflicts detected (default: True)
        resource_group_prefix: Prefix to add to all resource group names
        source_tenant_id: Source tenant ID (auto-detected from Azure CLI if not specified)
        target_tenant_id: Target tenant ID for cross-tenant deployment
        identity_mapping_file: Path to identity mapping JSON file for Entra ID object translation
        strict_translation: Fail on missing identity mappings (default: warn only)
        auto_import_existing: Automatically import pre-existing Azure resources (Issue #412)
        import_strategy: Strategy for importing resources (resource_groups, all_resources, selective)
        auto_register_providers: Automatically register required Azure resource providers
        scan_target: Enable smart import by scanning target tenant (Phase 1F)
        scan_target_tenant_id: Target tenant ID to scan (required if scan_target is True)
        scan_target_subscription_id: Optional target subscription ID to scan
        split_by_community: Split resources into separate Terraform files per community

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    try:
        # Initialize generation metrics (Issue #413)
        metrics = GenerationMetrics()

        logger.info("🏗️ Starting IaC generation")
        logger.info(f"Format: {format_type}")

        # Get Neo4j driver
        driver = get_neo4j_driver_from_config()

        # Create GraphTraverser
        traverser = GraphTraverser(driver, [])

        # Build filter if provided
        filter_cypher = None

        # Handle node_ids filter
        if node_ids:
            # Get specified nodes and all their connected nodes
            node_id_list = ", ".join([f"'{nid}'" for nid in node_ids])
            filter_cypher = f"""
            MATCH (n)
            WHERE n.id IN [{node_id_list}]
            OPTIONAL MATCH (n)-[rel]-(connected)
            WITH n, collect(DISTINCT {{
                type: type(rel),
                target: connected.id,
                original_type: rel.original_type,
                narrative_context: rel.narrative_context
            }}) AS rels
            RETURN n AS r, rels
            """
        elif resource_filters:
            # Parse resource_filters to support both type-based and property-based filtering
            # Format examples:
            #   - Type filter: "Microsoft.Network/virtualNetworks"
            #   - Property filter: "resourceGroup=~'(?i).*(simuland|SimuLand).*'"
            #   - Multiple filters: "Microsoft.Network/virtualNetworks,resourceGroup='myRG'"

            filters = [f.strip() for f in resource_filters.split(",")]
            filter_conditions = []

            for f in filters:
                if "=" in f:
                    # Property-based filter (e.g., "resourceGroup=~'pattern'" or "resourceGroup='exact'")
                    # Check for regex operator first
                    is_regex = "=~" in f

                    if is_regex:
                        # Split on =~ for regex patterns
                        prop_name, pattern = f.split("=~", 1)
                        prop_name = prop_name.strip()
                        pattern = pattern.strip()
                    else:
                        # Split on = for exact matches
                        prop_name, pattern = f.split("=", 1)
                        prop_name = prop_name.strip()
                        pattern = pattern.strip()

                    # Handle both resourceGroup and resource_group property names
                    if prop_name.lower() in ("resourcegroup", "resource_group"):
                        # Support both field names in Neo4j
                        if is_regex:
                            filter_conditions.append(
                                f"(r.resource_group =~ {pattern} OR r.resourceGroup =~ {pattern})"
                            )
                        else:
                            filter_conditions.append(
                                f"(r.resource_group = {pattern} OR r.resourceGroup = {pattern})"
                            )
                    else:
                        # Generic property filter
                        if is_regex:
                            filter_conditions.append(f"r.{prop_name} =~ {pattern}")
                        else:
                            filter_conditions.append(f"r.{prop_name} = {pattern}")
                else:
                    # Type-based filter (backward compatible)
                    filter_conditions.append(f"r.type = '{f}'")

            filter_cypher = f"""
            MATCH (r:Resource)
            WHERE {" OR ".join(filter_conditions)}
            OPTIONAL MATCH (r)-[rel]->(t:Resource)
            RETURN r, collect({{
                type: type(rel),
                target: t.id,
                original_type: rel.original_type,
                narrative_context: rel.narrative_context
            }}) AS rels
            """

            logger.info(f"Applying resource filters: {', '.join(filters)}")
            logger.debug(f"Generated filter Cypher: {filter_cypher}")

        # Traverse graph
        graph = await traverser.traverse(filter_cypher)
        logger.info(f"Extracted {len(graph.resources)} resources")

        # Collect source analysis metrics (Issue #413)
        metrics.source_resources_scanned = len(graph.resources)

        # Analyze resource types for metrics (Issue #413)
        non_deployable_types = {
            "Microsoft.Resources/subscriptions",
            "Microsoft.Resources/tenants",
            "Microsoft.Resources/resourceGroups",
            "Subscription",
            "Tenant",
            "ResourceGroup",
        }

        # Get emitter to check supported types
        temp_emitter_cls = get_emitter(format_type)
        if format_type.lower() == "terraform":
            temp_emitter = temp_emitter_cls()
            # Use hasattr to check for terraform-specific attribute
            if hasattr(temp_emitter, "AZURE_TO_TERRAFORM_MAPPING"):
                supported_types = set(temp_emitter.AZURE_TO_TERRAFORM_MAPPING.keys())  # type: ignore[attr-defined]
            else:
                supported_types = set()
        else:
            supported_types = set()

        # Analyze each resource
        unsupported_by_type = {}
        for resource in graph.resources:
            resource_type = resource.get("type", "unknown")
            resource_name = resource.get("name", "unknown")

            # Categorize resource
            if resource_type in non_deployable_types:
                metrics.source_non_deployable += 1
            elif (
                supported_types
                and resource_type not in supported_types
                and not resource_type.startswith("Microsoft.Graph/")
                and not resource_type.startswith("Microsoft.AAD/")
            ):
                # Unsupported type
                metrics.source_unsupported += 1
                if resource_type not in unsupported_by_type:
                    unsupported_by_type[resource_type] = []
                if len(unsupported_by_type[resource_type]) < 3:  # Keep up to 3 examples
                    unsupported_by_type[resource_type].append(resource_name)
            else:
                # Deployable
                metrics.source_deployable += 1

        # Store unsupported type info
        for resource_type, examples in unsupported_by_type.items():
            metrics.unsupported_types[resource_type] = UnsupportedTypeInfo(
                resource_type=resource_type,
                count=len(
                    [r for r in graph.resources if r.get("type") == resource_type]
                ),
                examples=examples,
            )

        # Smart import workflow (Phase 1F)
        comparison_result = None
        if scan_target:
            # Validate required parameters
            if not scan_target_tenant_id:
                logger.error(
                    "--scan-target-tenant-id required when --scan-target is enabled"
                )
                click.echo(
                    "Error: --scan-target-tenant-id is required when using --scan-target",
                    err=True,
                )
                return 1

            try:
                # Bug #14 fix: Extract source_subscription_id BEFORE using it
                # Extract from graph resources
                source_subscription_id = None
                if graph.resources:
                    for resource in graph.resources:
                        resource_id = resource.get("id", "")
                        if "/subscriptions/" in resource_id:
                            source_subscription_id = resource_id.split("/subscriptions/")[
                                1
                            ].split("/")[0]
                            logger.debug(
                                f"Extracted source subscription from resource ID: {source_subscription_id}"
                            )
                            break

                # 1. Scan target tenant
                import os

                from azure.identity import (
                    ClientSecretCredential,
                    DefaultAzureCredential,
                )

                from ..services.azure_discovery_service import AzureDiscoveryService
                from .resource_comparator import ResourceComparator
                from .target_scanner import TargetScannerService

                logger.info(f"Scanning target tenant: {scan_target_tenant_id}")
                click.echo(
                    f"Scanning target tenant for existing resources: {scan_target_tenant_id}"
                )

                # Create credential scoped to TARGET tenant
                target_credential = None

                # Try to get tenant-specific credentials from environment
                # Format: AZURE_TENANT_2_CLIENT_ID, AZURE_TENANT_2_CLIENT_SECRET
                target_client_id = os.getenv("AZURE_TENANT_2_CLIENT_ID")
                target_client_secret = os.getenv("AZURE_TENANT_2_CLIENT_SECRET")

                if target_client_id and target_client_secret:
                    logger.info(f"Using tenant-specific credentials for target tenant {scan_target_tenant_id}")
                    target_credential = ClientSecretCredential(
                        tenant_id=scan_target_tenant_id,
                        client_id=target_client_id,
                        client_secret=target_client_secret,
                    )
                else:
                    logger.warning(
                        "No tenant-specific credentials found (AZURE_TENANT_2_CLIENT_ID/SECRET). "
                        "Falling back to DefaultAzureCredential - this may fail if not authenticated to target tenant."
                    )
                    target_credential = DefaultAzureCredential()

                # Create config for AzureDiscoveryService with target tenant ID
                discovery_config = create_neo4j_config_from_env()
                discovery_config.tenant_id = scan_target_tenant_id

                # Create discovery service with target tenant credential
                discovery = AzureDiscoveryService(
                    config=discovery_config,
                    credential=target_credential
                )
                scanner = TargetScannerService(discovery)

                target_scan = await scanner.scan_target_tenant(
                    scan_target_tenant_id,
                    subscription_id=scan_target_subscription_id,
                )

                if target_scan.error:
                    logger.warning(f"Target scan had errors: {target_scan.error}")
                    logger.warning("Falling back to standard IaC generation")
                    click.echo(
                        f"Warning: Target scan encountered errors: {target_scan.error}",
                        err=True,
                    )
                    click.echo("Continuing with standard IaC generation...", err=True)
                else:
                    # 2. Compare using ResourceComparator
                    from src.utils.session_manager import Neo4jSessionManager

                    neo4j = Neo4jSessionManager(config=discovery_config.neo4j)
                    neo4j.connect()

                    # Bug #13 fix: Pass subscription IDs for cross-tenant ID normalization
                    comparator = ResourceComparator(
                        neo4j,
                        source_subscription_id=source_subscription_id,
                        target_subscription_id=scan_target_subscription_id,
                    )

                    logger.info("Comparing abstracted graph with target scan")
                    click.echo("Analyzing differences between source and target...")

                    comparison_result = comparator.compare_resources(
                        abstracted_resources=graph.resources,
                        target_scan=target_scan,
                    )

                    # Log summary
                    summary = comparison_result.summary
                    logger.info(
                        f"Comparison complete: "
                        f"{summary.get('new', 0)} new, "
                        f"{summary.get('exact_match', 0)} exact matches, "
                        f"{summary.get('drifted', 0)} drifted, "
                        f"{summary.get('orphaned', 0)} orphaned"
                    )
                    click.echo(
                        f"Comparison results: {summary.get('new', 0)} new resources, "
                        f"{summary.get('exact_match', 0)} exact matches, "
                        f"{summary.get('drifted', 0)} with drift, "
                        f"{summary.get('orphaned', 0)} orphaned in target"
                    )

            except Exception as e:
                logger.error(f"Smart import failed: {e}", exc_info=True)
                logger.warning("Falling back to standard IaC generation")
                click.echo(
                    f"Warning: Smart import failed: {e}. "
                    f"Continuing with standard IaC generation...",
                    err=True,
                )
                comparison_result = None

        # Determine target subscription ID
        # Priority: 1) Explicit --target-subscription parameter
        #           2) AZURE_SUBSCRIPTION_ID environment variable
        #           3) Extract from resource IDs (source subscription)
        import os

        subscription_id = target_subscription or os.environ.get("AZURE_SUBSCRIPTION_ID")

        if not subscription_id and graph.resources:
            # Fallback: extract from first resource with subscription in ID (SOURCE subscription)
            for resource in graph.resources:
                resource_id = resource.get("id", "")
                if "/subscriptions/" in resource_id:
                    subscription_id = resource_id.split("/subscriptions/")[1].split(
                        "/"
                    )[0]
                    logger.warning(
                        f"No target subscription specified - using subscription from source resource: {subscription_id}. "
                        f"Use --target-subscription to deploy to a different subscription."
                    )
                    break

        if subscription_id:
            logger.info(f"Using target subscription: {subscription_id}")
        else:
            logger.warning(
                "No subscription ID available. Key Vault tenant_id will use placeholder. "
                "Set AZURE_SUBSCRIPTION_ID environment variable, use --target-subscription parameter, "
                "or ensure resource IDs contain subscription."
            )

        # Determine source subscription and tenant IDs for cross-tenant translation
        # Priority: 1) Explicit parameters
        #           2) Azure CLI defaults
        #           3) Extract from resource IDs
        source_subscription_id = None
        resolved_source_tenant_id = source_tenant_id
        resolved_target_tenant_id = target_tenant_id

        # Try to get defaults from Azure CLI if not explicitly provided
        if not resolved_source_tenant_id or not source_subscription_id:
            cli_info = _get_default_subscription_from_azure_cli()
            if cli_info:
                cli_sub_id, cli_tenant_id = cli_info
                if not source_subscription_id:
                    source_subscription_id = cli_sub_id
                    logger.debug(
                        f"Using source subscription from Azure CLI: {source_subscription_id}"
                    )
                if not resolved_source_tenant_id:
                    resolved_source_tenant_id = cli_tenant_id
                    logger.debug(
                        f"Using source tenant from Azure CLI: {resolved_source_tenant_id}"
                    )

        # Fallback: extract source subscription from resource IDs if still not set
        if not source_subscription_id and graph.resources:
            for resource in graph.resources:
                resource_id = resource.get("id", "")
                if "/subscriptions/" in resource_id:
                    source_subscription_id = resource_id.split("/subscriptions/")[
                        1
                    ].split("/")[0]
                    logger.debug(
                        f"Extracted source subscription from resource ID: {source_subscription_id}"
                    )
                    break

        # Bug #93: Fallback for source tenant ID when Azure CLI not available
        # If target tenant is specified but source tenant is unknown, and there are no
        # explicit cross-tenant indicators (identity mapping file), assume same-tenant deployment
        if (
            not resolved_source_tenant_id
            and resolved_target_tenant_id
            and not identity_mapping_file
        ):
            resolved_source_tenant_id = resolved_target_tenant_id
            logger.info(
                f"No source tenant specified and Azure CLI unavailable. "
                f"Defaulting to same-tenant deployment (source = target = {resolved_target_tenant_id})"
            )

        # Log cross-tenant translation status
        if resolved_target_tenant_id and resolved_source_tenant_id:
            if resolved_target_tenant_id != resolved_source_tenant_id:
                logger.info(
                    f"Cross-tenant translation enabled: {resolved_source_tenant_id} -> {resolved_target_tenant_id}"
                )
            else:
                logger.info(
                    "Source and target tenants are the same - translation not needed"
                )
        elif resolved_target_tenant_id:
            logger.warning(
                "Target tenant specified but source tenant unknown - cross-tenant translation may not work correctly"
            )

        # Auto-map identities for cross-tenant deployment (Issue #410)
        identity_mapping = None
        if resolved_target_tenant_id and resolved_source_tenant_id:
            if resolved_target_tenant_id != resolved_source_tenant_id:
                logger.info("Automatically mapping identities between tenants...")
                click.echo("Creating identity mappings between tenants...")

                mapper = AutoIdentityMapper()
                try:
                    # Create auto-mapping (manual file takes precedence if provided)
                    identity_mapping = await mapper.create_mapping(
                        source_tenant_id=resolved_source_tenant_id,
                        target_tenant_id=resolved_target_tenant_id,
                        manual_mapping_file=(
                            Path(identity_mapping_file)
                            if identity_mapping_file
                            else None
                        ),
                        neo4j_driver=driver,
                    )

                    # Save mapping to output directory for reference
                    if output_path:
                        mapping_output_dir = validate_output_path(output_path)
                    else:
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        mapping_output_dir = Path("outputs") / f"iac-out-{timestamp}"

                    mapping_output_dir.mkdir(parents=True, exist_ok=True)
                    mapping_file = mapping_output_dir / "identity_mapping.json"
                    mapper.save_mapping(identity_mapping, mapping_file)

                    # Update identity_mapping_file to point to generated file if not manually provided
                    if not identity_mapping_file:
                        identity_mapping_file = str(mapping_file)

                    click.echo(f"Identity mapping saved to: {mapping_file}")

                    # Log mapping summary
                    users_count = len(identity_mapping["users"])
                    groups_count = len(identity_mapping["groups"])
                    sps_count = len(identity_mapping["service_principals"])
                    click.echo(
                        f"Mapped {users_count} users, {groups_count} groups, {sps_count} service principals"
                    )

                    # Collect translation metrics (Issue #413)
                    metrics.translation_enabled = True
                    metrics.translation_users_mapped = users_count
                    metrics.translation_groups_mapped = groups_count
                    metrics.translation_sps_mapped = sps_count
                    metrics.translation_identities_mapped = (
                        users_count + groups_count + sps_count
                    )

                except Exception as e:
                    logger.error(f"Identity mapping failed: {e}")
                    click.echo(
                        f"Warning: Automatic identity mapping failed: {e}",
                        err=True,
                    )
                    click.echo(
                        "Continuing with manual identity mapping file if provided...",
                        err=True,
                    )

        # Pre-deployment conflict detection (Issue #336)
        should_check_conflicts = check_conflicts and not skip_conflict_check
        if should_check_conflicts and subscription_id and not dry_run:
            import os

            from azure.identity import ClientSecretCredential

            from .cleanup_integration import invoke_cleanup_script, parse_cleanup_result
            from .conflict_detector import ConflictDetector

            logger.info("Running pre-deployment conflict detection...")
            click.echo("Checking for deployment conflicts...")

            try:
                # Create credential for TARGET tenant (not source) for conflict detection
                target_tenant = resolved_target_tenant_id or resolved_source_tenant_id
                # Use target tenant credentials if different from source
                use_target_creds = resolved_target_tenant_id and resolved_target_tenant_id != resolved_source_tenant_id
                conflict_detector_credential = ClientSecretCredential(
                    tenant_id=target_tenant,
                    client_id=os.getenv("AZURE_TENANT_2_CLIENT_ID") if use_target_creds else os.getenv("AZURE_CLIENT_ID"),
                    client_secret=os.getenv("AZURE_TENANT_2_CLIENT_SECRET") if use_target_creds else os.getenv("AZURE_CLIENT_SECRET"),
                )

                # Initialize detector with proper credential
                detector = ConflictDetector(subscription_id, credential=conflict_detector_credential)

                # Detect conflicts
                conflict_report = await detector.detect_conflicts(graph.resources)

                # Display conflict report
                click.echo(conflict_report.format_report())

                # Handle conflicts
                if conflict_report.has_conflicts:
                    if auto_cleanup:
                        click.echo("\nAttempting automatic cleanup...")
                        try:
                            cleanup_result = invoke_cleanup_script(
                                subscription_id,
                                dry_run=False,
                                force=True,
                            )
                            parsed = parse_cleanup_result(cleanup_result)

                            if parsed["success"]:
                                click.echo(
                                    f"Auto-cleanup completed: {len(parsed['resources_deleted'])} resources deleted"
                                )
                                # Re-run conflict check
                                conflict_report = await detector.detect_conflicts(
                                    graph.resources
                                )
                                if conflict_report.has_conflicts:
                                    click.echo(
                                        f"Warning: {len(conflict_report.conflicts)} conflicts remain after cleanup"
                                    )
                                else:
                                    click.echo("All conflicts resolved")
                            else:
                                click.echo(
                                    f"Auto-cleanup failed with {len(parsed['errors'])} errors"
                                )
                                if parsed["errors"]:
                                    for error in parsed["errors"][:5]:  # Show first 5
                                        click.echo(f"  • {error}")

                        except Exception as e:
                            logger.error(f"Auto-cleanup failed: {e}")
                            click.echo(f"Auto-cleanup failed: {e}")

                    if conflict_report.has_conflicts and fail_on_conflicts:
                        click.echo("\nCannot proceed with deployment due to conflicts")
                        click.echo("\nOptions:")
                        click.echo("  1. Run: ./scripts/cleanup_target_subscription.sh")
                        click.echo(
                            "  2. Use: --auto-cleanup to run cleanup automatically"
                        )
                        click.echo(
                            "  3. Use: --naming-suffix <suffix> to rename resources"
                        )
                        click.echo(
                            "  4. Use: --skip-conflict-check to bypass (not recommended)"
                        )
                        return 1
                    elif conflict_report.has_conflicts:
                        click.echo(
                            "\nWarning: Conflicts detected but continuing (fail_on_conflicts=False)"
                        )
                else:
                    click.echo(
                        "No conflicts detected, proceeding with IaC generation\n"
                    )

            except Exception as e:
                logger.warning(f"Conflict detection failed: {e}")
                click.echo(
                    f"Warning: Conflict detection failed: {e}. Proceeding anyway..."
                )
        elif should_check_conflicts and not subscription_id:
            logger.warning("AZURE_SUBSCRIPTION_ID not set, skipping conflict detection")
        elif skip_conflict_check:
            logger.info("Conflict detection skipped (--skip-conflict-check)")

        # Handle Key Vault soft-delete conflicts (GAP-016 / GitHub issue #325)
        # Always check for conflicts, optionally purge based on flag
        from .keyvault_handler import KeyVaultHandler

        vault_resources = [
            r for r in graph.resources if r.get("type") == "Microsoft.KeyVault/vaults"
        ]

        if vault_resources:
            logger.info(f"Found {len(vault_resources)} Key Vault resources")
            vault_names = [r.get("name") for r in vault_resources if r.get("name")]

            if vault_names and subscription_id:
                handler = KeyVaultHandler()
                try:
                    name_mapping = handler.handle_vault_conflicts(
                        vault_names,
                        subscription_id,
                        location=location,
                        auto_purge=auto_purge_soft_deleted,
                    )

                    # Apply name mappings to resources
                    if name_mapping:
                        for resource in vault_resources:
                            old_name = resource.get("name")
                            if old_name in name_mapping:
                                new_name = name_mapping[old_name]
                                resource["name"] = new_name
                                logger.warning(
                                    f"Renamed Key Vault due to soft-delete conflict: "
                                    f"{old_name} -> {new_name}"
                                )
                except Exception as e:
                    logger.warning(
                        f"Key Vault conflict handling failed: {e}. "
                        f"Proceeding with original names."
                    )
            elif vault_names and not subscription_id:
                logger.warning(
                    "AZURE_SUBSCRIPTION_ID not set, skipping Key Vault "
                    "soft-delete conflict check"
                )

        # Apply transformations
        engine = TransformationEngine(rules_file, aad_mode="manual")

        # Subset filtering
        subset_filter_obj = None
        if subset_filter:
            subset_filter_obj = SubsetFilter.parse(subset_filter)
            logger.info(f"Using subset filter: {subset_filter_obj}")

        # Generate templates using new engine method if subset or RG is specified
        if subset_filter_obj or dest_rg or location or preserve_rg_structure:
            emitter_cls = get_emitter(format_type)
            # Pass cross-tenant translation parameters to emitter (only for Terraform)
            if format_type.lower() == "terraform":
                # Create credential for TARGET tenant (not source)
                import os

                from azure.identity import ClientSecretCredential
                target_tenant = resolved_target_tenant_id or resolved_source_tenant_id
                # Use target tenant credentials if different from source
                use_target_creds = resolved_target_tenant_id and resolved_target_tenant_id != resolved_source_tenant_id
                credential = ClientSecretCredential(
                    tenant_id=target_tenant,
                    client_id=os.getenv("AZURE_TENANT_2_CLIENT_ID") if use_target_creds else os.getenv("AZURE_CLIENT_ID"),
                    client_secret=os.getenv("AZURE_TENANT_2_CLIENT_SECRET") if use_target_creds else os.getenv("AZURE_CLIENT_SECRET"),
                )

                emitter = emitter_cls(  # pyright: ignore[reportCallIssue]
                    resource_group_prefix=resource_group_prefix,
                    target_subscription_id=subscription_id,
                    target_tenant_id=resolved_target_tenant_id,
                    source_subscription_id=source_subscription_id,
                    source_tenant_id=resolved_source_tenant_id,
                    identity_mapping_file=identity_mapping_file,
                    strict_mode=strict_translation,
                    auto_import_existing=auto_import_existing,
                    import_strategy=import_strategy,
                    credential=credential,
                )
            else:
                emitter = emitter_cls(resource_group_prefix=resource_group_prefix)
            if output_path:
                out_dir = validate_output_path(output_path)
            else:
                out_dir = default_timestamped_dir()

            # Log RG preservation mode (GAP-017)
            if preserve_rg_structure:
                logger.info(
                    "Preserving source resource group structure in target deployment"
                )

            # Pass RG, location, tenant_id, and subscription_id to engine.generate_iac (GAP-331)
            paths = engine.generate_iac(
                graph,
                emitter,
                out_dir,
                subset_filter=subset_filter_obj,
                validate_subnet_containment=not skip_subnet_validation,
                auto_fix_subnets=auto_fix_subnets,
                validate_address_spaces=not skip_address_space_validation,
                auto_renumber_conflicts=auto_renumber_address_spaces,
                tenant_id=tenant_id,
                subscription_id=subscription_id,
            )
            click.echo(f"✅ Wrote {len(paths)} files to {out_dir}")
            for path in paths:
                click.echo(f"  📄 {path}")

            # Collect metrics for early return path (Issue #413)
            if format_type.lower() == "terraform" and hasattr(
                emitter, "get_resource_count"
            ):
                metrics.terraform_resources_generated = emitter.get_resource_count()  # type: ignore[attr-defined]
                metrics.terraform_files_created = emitter.get_files_created_count()  # type: ignore[attr-defined]

                # Track import blocks if generated (Issue #412)
                if hasattr(emitter, "get_import_blocks_count"):
                    import_count = emitter.get_import_blocks_count()  # type: ignore[attr-defined]
                    if import_count > 0:
                        metrics.import_enabled = True
                        metrics.import_strategy = emitter.import_strategy  # type: ignore[attr-defined]
                        metrics.import_commands_generated = import_count
                translation_stats = emitter.get_translation_stats()  # type: ignore[attr-defined]
                if translation_stats:
                    metrics.translation_enabled = True
                    metrics.translation_users_mapped = translation_stats.get(
                        "users_mapped", 0
                    )
                    metrics.translation_groups_mapped = translation_stats.get(
                        "groups_mapped", 0
                    )
                    metrics.translation_sps_mapped = translation_stats.get(
                        "service_principals_mapped", 0
                    )
                    metrics.translation_identities_mapped = (
                        metrics.translation_users_mapped
                        + metrics.translation_groups_mapped
                        + metrics.translation_sps_mapped
                    )
                metrics.calculate_success_rate()

                # Generate and display report
                try:
                    report = GenerationReport(
                        metrics=metrics,
                        output_directory=out_dir,
                        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    )
                    click.echo(report.format_report())
                    report_path = report.save_to_file()
                    logger.info(f"Generation report saved to: {report_path}")
                except Exception as e:
                    logger.warning(f"Failed to generate report: {e}")

            return 0

        # Default: apply rules to all resources
        graph.resources = [engine.apply(r) for r in graph.resources]

        # Handle dry run
        if dry_run:
            sample_resources = graph.resources[:5]  # Show first 5 resources
            output_data = {
                "resources": sample_resources,
                "total_count": len(graph.resources),
                "format": format_type,
            }
            click.echo(json.dumps(output_data, indent=2, default=str))
            return 0

        # Get emitter
        emitter_cls = get_emitter(format_type)
        # Pass cross-tenant translation parameters to emitter (only for Terraform)
        if format_type.lower() == "terraform":
            # Create credential for TARGET tenant (not source)
            import os

            from azure.identity import ClientSecretCredential
            target_tenant = resolved_target_tenant_id or resolved_source_tenant_id
            # Use target tenant credentials if different from source
            use_target_creds = resolved_target_tenant_id and resolved_target_tenant_id != resolved_source_tenant_id
            credential = ClientSecretCredential(
                tenant_id=target_tenant,
                client_id=os.getenv("AZURE_TENANT_2_CLIENT_ID") if use_target_creds else os.getenv("AZURE_CLIENT_ID"),
                client_secret=os.getenv("AZURE_TENANT_2_CLIENT_SECRET") if use_target_creds else os.getenv("AZURE_CLIENT_SECRET"),
            )

            emitter = emitter_cls(  # pyright: ignore[reportCallIssue]
                resource_group_prefix=resource_group_prefix,
                target_subscription_id=subscription_id,
                target_tenant_id=resolved_target_tenant_id,
                source_subscription_id=source_subscription_id,
                source_tenant_id=resolved_source_tenant_id,
                identity_mapping_file=identity_mapping_file,
                strict_mode=strict_translation,
                auto_import_existing=auto_import_existing,
                import_strategy=import_strategy,
                credential=credential,
            )
        else:
            emitter = emitter_cls(resource_group_prefix=resource_group_prefix)

        # Determine output directory
        if output_path:
            out_dir = validate_output_path(output_path)
        else:
            out_dir = default_timestamped_dir()

        # Generate templates (pass preserve_rg_structure and tenant_id for Terraform emitter)
        # Check if emitter supports preserve_rg_structure and tenant_id parameters
        import inspect

        emit_signature = inspect.signature(emitter.emit)

        # Build kwargs for emit call based on supported parameters
        emit_kwargs = {"domain_name": domain_name}
        if "preserve_rg_structure" in emit_signature.parameters:
            emit_kwargs["preserve_rg_structure"] = preserve_rg_structure
        if "tenant_id" in emit_signature.parameters:
            emit_kwargs["tenant_id"] = tenant_id
        if "subscription_id" in emit_signature.parameters:
            emit_kwargs["subscription_id"] = subscription_id
        if "neo4j_driver" in emit_signature.parameters:
            emit_kwargs["neo4j_driver"] = driver
        if "comparison_result" in emit_signature.parameters:
            emit_kwargs["comparison_result"] = comparison_result
        if "split_by_community" in emit_signature.parameters:
            emit_kwargs["split_by_community"] = split_by_community

        paths = emitter.emit(graph, out_dir, **emit_kwargs)

        # Collect generation metrics from emitter (Issue #413)
        if format_type.lower() == "terraform" and hasattr(
            emitter, "get_resource_count"
        ):
            metrics.terraform_resources_generated = emitter.get_resource_count()  # type: ignore[attr-defined]
            metrics.terraform_files_created = emitter.get_files_created_count()  # type: ignore[attr-defined]

            # Track import blocks if generated (Issue #412)
            if hasattr(emitter, "get_import_blocks_count"):
                import_count = emitter.get_import_blocks_count()  # type: ignore[attr-defined]
                if import_count > 0:
                    metrics.import_enabled = True
                    metrics.import_strategy = emitter.import_strategy  # type: ignore[attr-defined]
                    metrics.import_commands_generated = import_count

            # Get translation stats if available
            translation_stats = emitter.get_translation_stats()  # type: ignore[attr-defined]
            if translation_stats:
                metrics.translation_enabled = True
                metrics.translation_users_mapped = translation_stats.get(
                    "users_mapped", 0
                )
                metrics.translation_groups_mapped = translation_stats.get(
                    "groups_mapped", 0
                )
                metrics.translation_sps_mapped = translation_stats.get(
                    "service_principals_mapped", 0
                )
                metrics.translation_identities_mapped = (
                    metrics.translation_users_mapped
                    + metrics.translation_groups_mapped
                    + metrics.translation_sps_mapped
                )

        # Calculate success rate (Issue #413)
        metrics.calculate_success_rate()

        # Validate and fix global name conflicts (GAP-014)
        # Skip validation when smart import is enabled (it handles conflicts)
        if scan_target:
            logger.info(
                "Skipping name conflict validation (smart import mode enabled)"
            )
        elif format_type.lower() == "terraform" and not skip_name_validation:
            from ..validation import NameConflictValidator

            logger.info("🔍 Checking for global resource name conflicts...")

            # Read generated Terraform config
            terraform_file = out_dir / "main.tf.json"
            if terraform_file.exists():
                with open(terraform_file) as f:
                    terraform_config = json.load(f)

                # Initialize validator (GAP-015, GAP-016)
                subscription_id = None  # TODO: Get from environment/config
                validator = NameConflictValidator(
                    subscription_id=subscription_id,
                    naming_suffix=naming_suffix,
                    preserve_names=preserve_names,
                    auto_purge_soft_deleted=auto_purge_soft_deleted,
                )

                # Validate and auto-fix conflicts (respects preserve_names mode)
                auto_fix = not preserve_names  # Don't auto-fix if preserving names
                updated_config, validation_result = (
                    validator.validate_and_fix_terraform(
                        terraform_config, auto_fix=auto_fix
                    )
                )

                # Report conflicts (GAP-015)
                if validation_result.conflicts:
                    if preserve_names:
                        # In preserve-names mode, fail on conflicts
                        click.echo(
                            f"❌ Found {len(validation_result.conflicts)} name conflicts (preserve-names mode):"
                        )
                        for conflict in validation_result.conflicts:
                            click.echo(
                                f"   • {conflict.resource_type}: {conflict.original_name}"
                            )
                            click.echo(f"     Reason: {conflict.conflict_reason}")
                        click.echo(
                            "\n💡 Tip: Remove --preserve-names flag to auto-fix conflicts, "
                            "or use --naming-suffix to specify a custom suffix."
                        )
                        return 1
                    else:
                        # In auto-fix mode, show fixes
                        click.echo(
                            f"⚠️  Found {len(validation_result.conflicts)} name conflicts:"
                        )
                        for conflict in validation_result.conflicts:
                            click.echo(
                                f"   • {conflict.resource_type}: {conflict.original_name} "
                                f"-> {conflict.suggested_name or 'N/A'}"
                            )
                            click.echo(f"     Reason: {conflict.conflict_reason}")

                # Save updated config if changes were made
                if validation_result.name_mappings:
                    with open(terraform_file, "w") as f:
                        json.dump(updated_config, f, indent=2)

                    # Save name mappings with conflict reasons (GAP-015)
                    validator.save_name_mappings(
                        validation_result.name_mappings,
                        out_dir,
                        conflicts=validation_result.conflicts,
                    )
                    click.echo(
                        f"✅ Auto-fixed {len(validation_result.name_mappings)} conflicts"
                    )
                    click.echo(
                        f"   Name mappings saved to {out_dir / 'name_mappings.json'}"
                    )
                else:
                    click.echo("✅ No global name conflicts detected")

        click.echo(f"✅ Wrote {len(paths)} files to {paths[0].parent}")
        for path in paths:
            click.echo(f"  📄 {path}")

        # Check Azure resource provider registration (before validation/deployment)
        # Use target_subscription if provided (cross-tenant), otherwise use source subscription
        provider_check_subscription = target_subscription if target_subscription else subscription_id
        if format_type.lower() == "terraform" and provider_check_subscription and not dry_run:
            from .provider_manager import ProviderManager

            try:
                logger.info(f"Checking Azure resource provider registration in subscription {provider_check_subscription}...")

                # Bug #19 fix: Use target tenant credentials for cross-tenant provider registration
                provider_credential = None
                if target_tenant_id and provider_check_subscription == target_subscription:
                    # Cross-tenant mode - use target tenant credentials
                    target_client_id = os.getenv("AZURE_TENANT_2_CLIENT_ID")
                    target_client_secret = os.getenv("AZURE_TENANT_2_CLIENT_SECRET")

                    if target_client_id and target_client_secret:
                        from azure.identity import ClientSecretCredential
                        provider_credential = ClientSecretCredential(
                            tenant_id=target_tenant_id,
                            client_id=target_client_id,
                            client_secret=target_client_secret,
                        )
                        logger.info(f"Using target tenant credentials for provider registration in {target_tenant_id}")
                    else:
                        logger.warning("No target tenant credentials found (AZURE_TENANT_2_CLIENT_ID/SECRET). Provider registration may fail.")

                provider_manager = ProviderManager(
                    subscription_id=provider_check_subscription,
                    credential=provider_credential,
                )
                provider_report = await provider_manager.validate_before_deploy(
                    terraform_path=out_dir,
                    auto_register=auto_register_providers,
                )

                # Display report
                click.echo(provider_report.format_report())

                # Warn if any providers failed to register
                if provider_report.failed_providers:
                    click.echo(
                        f"⚠️  Warning: {len(provider_report.failed_providers)} providers "
                        f"failed to register. Deployment may fail."
                    )

            except Exception as e:
                logger.warning(f"Provider check failed: {e}")
                click.echo(
                    f"⚠️  Warning: Provider check failed: {e}. Proceeding anyway...",
                    err=True,
                )

        # Validate Terraform if format is terraform and not skipped
        if format_type.lower() == "terraform" and not skip_validation:
            from .validators import TerraformValidator

            logger.info("Running Terraform validation...")
            validator = TerraformValidator()
            validation_result = validator.validate(out_dir)

            if not validation_result.valid:
                # Handle validation failure
                keep_files = validator.handle_failure(validation_result)
                if not keep_files:
                    # Cleanup files
                    import shutil

                    shutil.rmtree(out_dir)
                    click.echo("🗑️  Removed invalid IaC files")
                    return 1
            else:
                click.echo("✅ Terraform validation passed")

        # Import pre-existing resources if requested (Issue #412)
        if (
            auto_import_existing
            and format_type.lower() == "terraform"
            and subscription_id
            and not dry_run
        ):
            await _handle_terraform_import(
                subscription_id=subscription_id,
                terraform_dir=out_dir,
                import_strategy_str=import_strategy,
            )

        # Register deployment if not a dry run
        if not dry_run:
            registry = DeploymentRegistry()

            # Count resources by type
            resource_counts = {}
            for resource in graph.resources:
                rtype = resource.get("type", "unknown")
                resource_counts[rtype] = resource_counts.get(rtype, 0) + 1

            # Determine tenant from environment
            tenant_name = "tenant-1"  # Default, could be enhanced with --tenant flag

            deployment_id = registry.register_deployment(
                directory=str(out_dir),
                tenant=tenant_name,
                resources=resource_counts,
                terraform_version=None,  # Could detect this
            )

            click.echo(f"📝 Registered deployment: {deployment_id}")
            click.echo("   Use 'atg undeploy' to destroy these resources")

        # Generate and display generation report (Issue #413)
        try:
            report = GenerationReport(
                metrics=metrics,
                output_directory=out_dir,
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            )

            # Display report
            click.echo(report.format_report())

            # Save report to file
            report_path = report.save_to_file()
            logger.info(f"Generation report saved to: {report_path}")

        except Exception as e:
            logger.warning(f"Failed to generate report: {e}")
            # Non-blocking - don't fail generation if reporting fails

        return 0

    except Exception as e:
        logger.error(f"❌ IaC generation failed: {e}", exc_info=True)
        click.echo(f"❌ Error: {e}", err=True)
        return 1
