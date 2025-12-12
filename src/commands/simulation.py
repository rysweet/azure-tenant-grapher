"""Simulation document generation command.

This module provides the 'generate-sim-doc' command for generating
simulated Azure customer profiles as Markdown narratives.

Issue #482: CLI Modularization
"""

import os
import sys
from datetime import datetime
from typing import Optional

import click
from rich.console import Console

from src.commands.base import async_command


@click.command("generate-sim-doc")
@click.option(
    "--size",
    type=int,
    required=False,
    help="Target company size (approximate number of employees)",
)
@click.option(
    "--seed",
    type=click.Path(exists=True, dir_okay=False, readable=True),
    required=False,
    help="Path to a markdown file with seed/suggestions for the profile",
)
@click.option(
    "--output",
    type=click.Path(dir_okay=False, writable=True),
    required=False,
    help="Output markdown file (default: outputs/simdoc-<timestamp>.md)",
)
@click.pass_context
@async_command
async def generate_sim_doc(
    ctx: click.Context,
    size: Optional[int],
    seed: Optional[str],
    output: Optional[str],
) -> None:
    """Generate a simulated Azure customer profile as a Markdown narrative."""
    await generate_sim_doc_command_handler(
        ctx, size=size, seed_path=seed, out_path=output
    )


async def generate_sim_doc_command_handler(
    ctx: click.Context,
    size: Optional[int] = None,
    seed_path: Optional[str] = None,
    out_path: Optional[str] = None,
) -> None:
    """
    Handler for 'generate-sim-doc' CLI command.
    Generates a simulated Azure customer profile document using LLM.
    """
    from src.llm_descriptions import create_llm_generator

    console = Console()

    # Load seed text if provided
    seed_text = ""
    if seed_path:
        try:
            with open(seed_path, encoding="utf-8") as f:
                seed_text = f.read()
        except Exception as e:
            click.echo(
                f"Failed to read seed file: {e}\n"
                "Action: Check that the seed file exists and is readable.",
                err=True,
            )
            sys.exit(1)

    # LLM generator
    llm = create_llm_generator()

    # Build the prompt
    prompt = _build_simulation_prompt(size, seed_text)

    # Generate the profile with streaming and progress indicator
    markdown = ""
    try:
        with console.status(
            "[bold green]Generating documentation...", spinner="dots"
        ) as status:
            first_token = True
            tokens = []
            try:
                async for token in llm.generate_description_streaming(prompt):
                    if first_token:
                        status.stop()
                        first_token = False
                    tokens.append(token)
                    console.print(token, end="", soft_wrap=True, highlight=False)
                markdown = "".join(tokens)
            except Exception as stream_exc:
                if first_token:
                    status.stop()
                console.print(
                    f"\n[red]Streaming failed, falling back to non-streaming mode: {stream_exc}[/red]"
                )
                try:
                    markdown = await llm.generate_sim_customer_profile(
                        size=size, seed=seed_text
                    )
                    console.print(markdown)
                except Exception as e:
                    click.echo(
                        f"LLM generation failed: {e}\n"
                        "Action: Check your Azure OpenAI configuration and network connectivity. Run with --log-level DEBUG for more details.",
                        err=True,
                    )
                    sys.exit(1)
    except Exception as e:
        click.echo(
            f"LLM generation failed: {e}\n"
            "Action: Check your Azure OpenAI configuration and network connectivity. Run with --log-level DEBUG for more details.",
            err=True,
        )
        sys.exit(1)

    # Determine output path (migrate simdocs/ to outputs/)
    effective_out_path = out_path
    if effective_out_path:
        output_path = effective_out_path
    else:
        os.makedirs("outputs", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_path = os.path.join("outputs", f"simdoc-{timestamp}.md")

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(markdown)
        console.print(
            f"\n[bold green]Simulated customer profile written to: {output_path}[/bold green]"
        )
    except Exception as e:
        click.echo(
            f"Failed to write output file: {e}\n"
            "Action: Check that the output path is writable and you have sufficient disk space.",
            err=True,
        )
        sys.exit(1)


def _build_simulation_prompt(size: Optional[int], seed_text: str) -> str:
    """Build the prompt for simulation generation."""
    # Calculate ranges based on size
    user_range = f"{int(size * 0.8)}-{int(size * 1.2)}" if size else "50-5000"
    group_range = f"{max(10, int(size * 0.1))}-{int(size * 0.3)}" if size else "10-200"
    sp_range = (
        f"{max(5, int(size * 0.02))}-{max(20, int(size * 0.05))}" if size else "5-50"
    )
    mi_range = (
        f"{max(3, int(size * 0.01))}-{max(10, int(size * 0.03))}" if size else "3-30"
    )
    ca_range = (
        f"{max(5, int(size * 0.01))}-{max(15, int(size * 0.02))}" if size else "5-20"
    )

    prompt = (
        "You are an expert Azure consultant. Generate a detailed, realistic simulated customer profile "
        "document for a fictional company that uses Microsoft Azure and Entra ID (formerly Azure AD). "
        "Focus on identity and access management configuration details.\n\n"
        "The document should include:\n\n"
        f"1. USERS ({user_range} total):\n"
        "   - Mix of different departments (IT, Finance, HR, Sales, Engineering, Marketing, Legal, Operations)\n"
        "   - Job titles that reflect realistic organizational hierarchy (Interns, Associates, Managers, Directors, VPs, C-suite)\n"
        "   - Last sign-in patterns (recent, stale, never)\n"
        "   - Include various user types: regular employees, executives, IT admins, contractors, external guests, service accounts\n"
        "   - Account statuses (active, disabled, locked)\n"
        "   - License assignments (E3, E5, F1, etc.)\n\n"
        f"2. GROUPS ({group_range} total):\n"
        "   - Different types: Security groups, Microsoft 365 groups, Distribution lists, Mail-enabled security groups\n"
        "   - Some with dynamic membership rules (e.g., department eq 'Sales', jobTitle contains 'Manager')\n"
        "   - Nested group structures showing inheritance\n"
        "   - Clear owners and members for each group\n"
        "   - Groups for different purposes: department teams, project groups, role-based access groups\n\n"
        f"3. SERVICE PRINCIPALS ({sp_range} total):\n"
        "   - Mix of first-party Microsoft apps and third-party integrations\n"
        "   - Various API permissions (Microsoft Graph, Azure AD Graph, SharePoint, etc.)\n"
        "   - Different authentication methods (certificates, client secrets, managed identities)\n"
        "   - Mix of application permissions and delegated permissions\n"
        "   - Include common scenarios: backup solutions, monitoring tools, CI/CD pipelines, SaaS integrations\n\n"
        f"4. MANAGED IDENTITIES ({mi_range} total):\n"
        "   - Both system-assigned and user-assigned identities\n"
        "   - Associated with specific Azure resources (VMs, App Services, Functions, AKS)\n"
        "   - Clear resource associations and permission scopes\n\n"
        "5. RBAC WITH PRIVILEGED IDENTITY MANAGEMENT (PIM):\n"
        "   - Mix of permanent and eligible role assignments\n"
        "   - Just-in-time (JIT) access patterns with activation requirements\n"
        "   - Approval workflows for privileged roles\n"
        "   - Time-bound assignments with start/end dates\n"
        "   - Various Azure RBAC roles (Owner, Contributor, Reader, custom roles)\n"
        "   - Azure AD roles (Global Admin, User Admin, Application Admin, etc.)\n"
        "   - Include role assignment conditions and justifications\n\n"
        f"6. CONDITIONAL ACCESS POLICIES ({ca_range} total):\n"
        "   - MFA requirements for specific apps or user groups\n"
        "   - Device compliance requirements (Intune enrolled, compliant, hybrid joined)\n"
        "   - Location-based access controls (trusted locations, country restrictions)\n"
        "   - Risk-based policies (sign-in risk, user risk)\n"
        "   - Session controls (app-enforced restrictions, limited access)\n"
        "   - Different policy states (enabled, disabled, report-only)\n\n"
        "7. ADDITIONAL IDENTITY SCENARIOS:\n"
        "   - B2B guest users from partner organizations\n"
        "   - Temporary contractor accounts with expiration dates\n"
        "   - Privileged access workstations (PAW) users\n"
        "   - Emergency break-glass accounts\n"
        "   - Synchronized on-premises accounts (hybrid identity)\n"
        "   - Application-specific service accounts\n\n"
        "For each identity-related entity, provide rich details that would exist in a real enterprise environment. "
        "Include realistic relationships between entities (e.g., users in groups, groups assigned to roles, service principals with specific permissions). "
        "Structure the output with clear sections and subsections, using a format that can be parsed to extract the identity and access management configuration. "
        "Include specific Azure AD object IDs (GUIDs) for all entities to enable relationship mapping."
    )
    if size:
        prompt += f"\n\nTarget company size: {size} employees (approximate)."
    if seed_text:
        prompt += f"\n\nSeed/suggestions for the profile:\n{seed_text}"

    return prompt


# Alias for gensimdoc command
gensimdoc = generate_sim_doc

# For backward compatibility
generate_sim_doc_command = generate_sim_doc
gensimdoc_command = gensimdoc

__all__ = [
    "generate_sim_doc",
    "generate_sim_doc_command",
    "generate_sim_doc_command_handler",
    "gensimdoc",
    "gensimdoc_command",
]
