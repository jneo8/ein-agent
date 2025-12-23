"""Orchestrates human-in-the-loop workflow execution."""

import asyncio
from typing import Optional

import typer
from rich.panel import Panel
from rich.prompt import Prompt
from temporalio.client import Client as TemporalClient

from ein_agent_cli import console
from ein_agent_cli.temporal import (
    trigger_human_in_loop_workflow,
    start_workflow_execution,
    provide_user_action,
    get_workflow_status,
    end_workflow,
)
from ein_agent_cli.models import (
    HumanInLoopConfig,
    WorkflowStatus,
    UserAction,
    ActionType,
)


async def run_human_in_loop(config: HumanInLoopConfig) -> None:
    """Orchestrate human-in-the-loop workflow execution.

    This function:
    1. Prompts user for initial task
    2. Triggers the workflow in Temporal
    3. Sends the initial user prompt
    4. Polls for status updates
    5. Prompts user for input when agent needs help
    6. Displays final report when execution completes

    Args:
        config: Human-in-the-loop configuration

    Raises:
        typer.Exit: On error or completion
    """
    try:
        console.print_header("Ein Agent - Human-in-the-Loop Workflow\n")

        # Display configuration
        console.print_dim(f"Temporal: {config.temporal.host}/{config.temporal.namespace}")
        console.print_newline()

        # Connect to Temporal
        client = await TemporalClient.connect(
            config.temporal.host,
            namespace=config.temporal.namespace,
        )

        # Check if user wants to connect to existing workflow or start new one
        workflow_id = None
        user_prompt = config.user_prompt

        if not user_prompt or user_prompt.strip() == "":
            console.print_info("What would you like the agent to help you with?")

            while True:
                user_input = Prompt.ask("You")

                # Handle special commands
                if user_input.strip() == "/help":
                    _display_help()
                    console.print_newline()
                    continue
                elif user_input.strip().startswith("/connect-workflow "):
                    # Extract workflow ID
                    workflow_id = user_input.strip()[len("/connect-workflow "):].strip()
                    if not workflow_id:
                        console.print_error("Please provide a workflow ID: /connect-workflow <workflow-id>")
                        continue

                    # Try to connect to existing workflow
                    console.print_info(f"Connecting to workflow: {workflow_id}")
                    try:
                        status = await get_workflow_status(client, workflow_id)
                        if status.state in ["completed", "failed"]:
                            console.print_error(f"Cannot connect: workflow is {status.state}")
                            workflow_id = None
                            continue

                        console.print_success(f"✓ Connected to workflow: {workflow_id}")
                        console.print_dim(f"Current state: {status.state}")
                        console.print_newline()
                        break
                    except Exception as e:
                        console.print_error(f"Failed to connect to workflow: {e}")
                        workflow_id = None
                        continue

                elif user_input.strip() == "/end" or not user_input or user_input.strip() == "":
                    console.print_warning("Exiting.")
                    raise typer.Exit(0)
                else:
                    # Valid task provided - start new workflow
                    user_prompt = user_input
                    break

        if workflow_id:
            # Connected to existing workflow - skip workflow creation
            console.print_info("Resuming conversation...")
            console.print_newline()
        else:
            # Start new workflow
            console.print_newline()
            console.print_info(f"Task: {user_prompt}")
            console.print_newline()

            # Trigger workflow
            console.print_info("Starting workflow...")
            workflow_id = await trigger_human_in_loop_workflow(
                user_prompt=user_prompt,
                config=config.temporal,
                workflow_id=config.workflow_id,
            )

            # Start execution
            await start_workflow_execution(
                client=client,
                workflow_id=workflow_id,
                user_prompt=user_prompt,
            )

            console.print_success("✓ Agent is now working on your task")
            console.print_newline()

        # Display workflow ID for future reconnection
        console.print_dim(f"Workflow ID: {workflow_id}")
        console.print_dim(f"(Use '/connect-workflow {workflow_id}' to resume this conversation later)")
        console.print_newline()

        # Interactive workflow loop
        iteration = 0
        while iteration < config.max_iterations:
            iteration += 1

            # Poll for status
            await asyncio.sleep(config.poll_interval)
            status = await get_workflow_status(client, workflow_id)

            # Handle different states
            if status.state == "executing":
                _display_executing_status(status, iteration)

            elif status.state == "awaiting_input":
                _display_awaiting_input_status(status)

                # Get user input
                action = await _get_user_action(status, client, workflow_id)

                if action is None:
                    # User wants to end workflow
                    console.print_warning("Ending workflow...")
                    await end_workflow(client, workflow_id)
                    break

                # Send action to workflow
                console.print_dim("Sending action to agent...")
                await provide_user_action(client, workflow_id, action)
                console.print_success("✓ Action sent")
                console.print_newline()

            elif status.state == "completed":
                _display_completed_status(status, workflow_id, config.temporal)
                break

            elif status.state == "failed":
                _display_failed_status(status)
                raise typer.Exit(1)

        if iteration >= config.max_iterations:
            console.print_warning(f"Maximum iterations ({config.max_iterations}) reached")
            console.print_info("Ending workflow...")
            await end_workflow(client, workflow_id)

    except typer.Exit:
        raise
    except Exception as e:
        console.print_error(f"✗ Error: {e}")
        raise typer.Exit(1)


def _display_executing_status(status: WorkflowStatus, iteration: int) -> None:
    """Display executing status.

    Args:
        status: Current workflow status
        iteration: Current iteration number
    """
    console.print_dim(f"[Iteration {iteration}] Agent is executing...")
    if status.findings:
        console.print_info(f"Progress: {len(status.findings)} finding(s)")


def _display_help() -> None:
    """Display available slash commands."""
    console.print_info("Available commands:")
    console.print_message("  /help                      - Show this help message")
    console.print_message("  /connect-workflow <id>     - Connect to an existing workflow")
    console.print_message("  /refresh                   - Get the latest workflow status")
    console.print_message("  /end                       - End the conversation and close the workflow")


def _display_awaiting_input_status(status: WorkflowStatus) -> None:
    """Display awaiting input status.

    Args:
        status: Current workflow status
    """
    console.print_newline()

    if status.current_question:
        # Display agent's response directly without extra formatting
        console.print_message(status.current_question)
        console.print_newline()

    if status.suggested_mcp_tools:
        console.print_dim(f"Suggested tools: {', '.join(status.suggested_mcp_tools)}")
        console.print_newline()


async def _get_user_action(status: WorkflowStatus, client: TemporalClient, workflow_id: str) -> Optional[UserAction]:
    """Get user action via interactive prompt.

    Users can:
    - Type their response directly (default: text response)
    - Type '/help' to see available commands
    - Type '/refresh' to get the latest workflow status
    - Type '/end' to end the workflow

    Args:
        status: Current workflow status
        client: Temporal client for querying workflow
        workflow_id: Current workflow ID

    Returns:
        UserAction or None if user wants to end
    """
    while True:
        content = Prompt.ask("You")

        # Handle special commands
        if content.strip() == "/help":
            _display_help()
            console.print_newline()
            continue
        elif content.strip() == "/refresh":
            # Get and display latest workflow status
            console.print_newline()
            console.print_info("Refreshing workflow status...")
            try:
                latest_status = await get_workflow_status(client, workflow_id)
                console.print_success(f"State: {latest_status.state}")

                if latest_status.current_question:
                    console.print_newline()
                    console.print_message(latest_status.current_question)

                if latest_status.suggested_mcp_tools:
                    console.print_dim(f"Suggested tools: {', '.join(latest_status.suggested_mcp_tools)}")

                console.print_newline()
            except Exception as e:
                console.print_error(f"Failed to refresh status: {e}")
                console.print_newline()
            continue
        elif content.strip() == "/end":
            return None
        else:
            # Default to text response for all input
            return UserAction(
                action_type=ActionType.TEXT,
                content=content,
                metadata={},
            )


def _display_completed_status(
    status: WorkflowStatus,
    workflow_id: str,
    temporal_config,
) -> None:
    """Display completed workflow status.

    Args:
        status: Current workflow status
        workflow_id: Workflow ID
        temporal_config: Temporal configuration
    """
    console.print_newline()
    console.print_bold_success("✓ Workflow Completed!")
    console.print_newline()

    if status.final_report:
        panel = Panel(
            status.final_report,
            title="Final Report",
            border_style="green",
        )
        console.print_table(panel)

    console.print_newline()
    console.print_info(f"Workflow ID: {workflow_id}")
    ui_host = temporal_config.host.split(':')[0]
    console.print_dim(
        f"View in Temporal UI: http://{ui_host}:8080/namespaces/{temporal_config.namespace}/workflows/{workflow_id}"
    )


def _display_failed_status(status: WorkflowStatus) -> None:
    """Display failed workflow status.

    Args:
        status: Current workflow status
    """
    console.print_newline()
    console.print_error("✗ Workflow Failed")

    if status.error_message:
        console.print_error(f"Error: {status.error_message}")
