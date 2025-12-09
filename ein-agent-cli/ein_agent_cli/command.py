"""Ein Agent CLI commands - entrypoint."""

import asyncio
from typing import List, Optional

import typer

from ein_agent_cli import orchestrator
from ein_agent_cli.models import WorkflowConfig

app = typer.Typer(help="Ein Agent CLI - Incident investigation and correlation")


@app.command()
def run_incident_workflow(
    alertmanager_url: str = typer.Option(
        "http://localhost:9093",
        "--alertmanager-url",
        "-a",
        help="Alertmanager URL",
    ),
    include: Optional[List[str]] = typer.Option(
        None,
        "--include",
        "-i",
        help="Alert names to include (whitelist). If not specified, all alerts are included.",
    ),
    mcp_servers: List[str] = typer.Option(
        ["kubernetes", "grafana"],
        "--mcp-server",
        "-m",
        help="MCP server names to use",
    ),
    temporal_host: str = typer.Option(
        None,
        "--temporal-host",
        help="Temporal server host:port",
    ),
    temporal_namespace: str = typer.Option(
        None,
        "--temporal-namespace",
        help="Temporal namespace",
    ),
    temporal_queue: str = typer.Option(
        None,
        "--temporal-queue",
        help="Temporal task queue",
    ),
    workflow_id: Optional[str] = typer.Option(
        None,
        "--workflow-id",
        help="Custom workflow ID",
    ),
    status: str = typer.Option(
        "firing",
        "--status",
        help="Filter alerts by status (firing/resolved/all)",
    ),
    blacklist: Optional[List[str]] = typer.Option(
        None,
        "--blacklist",
        "-b",
        help="Alert names to exclude (default: Watchdog). Use --blacklist '' to disable",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Query and filter alerts but don't trigger workflow",
    ),
):
    """Query Alertmanager and trigger incident correlation workflow.

    This command will:
    1. Query Alertmanager API for alerts
    2. Filter alerts by blacklist (default: Watchdog)
    3. Filter alerts by whitelist (if --include specified)
    4. Filter alerts by status (firing/resolved/all)
    5. Trigger IncidentCorrelationWorkflow in Temporal

    Examples:

      # Run with default settings (blacklists Watchdog, includes all others)
      ein-agent-cli run-incident-workflow

      # Include only specific alerts
      ein-agent-cli run-incident-workflow -i KubePodNotReady -i KubePodCrashLooping

      # Custom blacklist (exclude TargetDown and Watchdog)
      ein-agent-cli run-incident-workflow -b TargetDown -b Watchdog

      # Disable blacklist
      ein-agent-cli run-incident-workflow -b ''

      # Query remote Alertmanager
      ein-agent-cli run-incident-workflow -a http://alertmanager.example.com:9093

      # Dry run to see what would be triggered
      ein-agent-cli run-incident-workflow --dry-run
    """
    # Create workflow configuration from CLI arguments
    config = WorkflowConfig.from_cli_args(
        alertmanager_url=alertmanager_url,
        include=include,
        mcp_servers=mcp_servers,
        temporal_host=temporal_host,
        temporal_namespace=temporal_namespace,
        temporal_queue=temporal_queue,
        workflow_id=workflow_id,
        status=status,
        blacklist=blacklist,
        dry_run=dry_run,
    )

    # Run orchestrator with validated configuration
    asyncio.run(orchestrator.run_incident_workflow(config))
