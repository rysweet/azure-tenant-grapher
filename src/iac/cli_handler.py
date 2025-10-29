"""CLI handler for Infrastructure-as-Code generation commands.

This module provides the command handler for IaC generation functionality
in the Azure Tenant Grapher CLI.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import click
from neo4j import Driver  # type: ignore

from ..config_manager import create_neo4j_config_from_env
from ..deployment_registry import DeploymentRegistry
from ..utils.session_manager import create_session_manager
from .emitters import get_emitter
from .engine import TransformationEngine
from .subset import SubsetFilter
from .traverser import GraphTraverser

logger = logging.getLogger(__name__)


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

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    try:
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

        # Pre-deployment conflict detection (Issue #336)
        should_check_conflicts = check_conflicts and not skip_conflict_check
        if should_check_conflicts and subscription_id and not dry_run:
            from .cleanup_integration import invoke_cleanup_script, parse_cleanup_result
            from .conflict_detector import ConflictDetector

            logger.info("Running pre-deployment conflict detection...")
            click.echo("Checking for deployment conflicts...")

            try:
                # Initialize detector
                detector = ConflictDetector(subscription_id)

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
            emitter = emitter_cls(resource_group_prefix=resource_group_prefix)
            if output_path:
                out_dir = Path(output_path)
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
        emitter = emitter_cls(resource_group_prefix=resource_group_prefix)

        # Determine output directory
        if output_path:
            out_dir = Path(output_path)
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

        paths = emitter.emit(graph, out_dir, **emit_kwargs)

        # Validate and fix global name conflicts (GAP-014)
        if format_type.lower() == "terraform" and not skip_name_validation:
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

        return 0

    except Exception as e:
        logger.error(f"❌ IaC generation failed: {e}")
        click.echo(f"❌ Error: {e}", err=True)
        return 1
