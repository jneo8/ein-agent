"""Implementation of the /switch slash command."""
from prompt_toolkit import PromptSession
from rich.table import Table
from temporalio.client import Client as TemporalClient

from ein_agent_cli import console
from ein_agent_cli.models import HumanInLoopConfig, SessionState
from ein_agent_cli.slash_commands.base import (
    CommandResult,
    SlashCommand,
    WorkflowCompleter,
)
from ein_agent_cli.temporal import get_workflow_status, list_workflows


class SwitchCommand(SlashCommand):
    """Switch between connected workflows."""

    @property
    def name(self) -> str:
        return "switch"

    @property
    def description(self) -> str:
        return "Switch between workflows (shows running workflows with dropdown)"

    async def execute(
        self, args: str, config: HumanInLoopConfig, client: TemporalClient, session: SessionState
    ) -> CommandResult:
        # Get list of all workflows
        workflows = await list_workflows(config.temporal)

        if not workflows:
            console.print_info("No workflows found.")
            return CommandResult()

        # Display workflow table
        console.print_info("Available workflows:")
        console.print_newline()
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Workflow ID", style="cyan")
        table.add_column("Type", style="green")
        table.add_column("Started", style="yellow")
        table.add_column("Status", style="blue")

        for wf in workflows:
            wf_id = wf.get("workflow_id", "N/A")
            wf_type = wf.get("workflow_type", "N/A")
            start_time = wf.get("start_time", "N/A")
            status_marker = "[CURRENT]" if wf_id == session.current_workflow_id else ""

            table.add_row(
                wf_id, wf_type, start_time, f"{wf.get('status', 'N/A')} {status_marker}"
            )

        console.print_table(table)
        console.print_newline()

        # Create completer with workflow IDs
        completer = WorkflowCompleter(workflows, session.current_workflow_id)
        prompt_session = PromptSession(completer=completer)

        # Determine default workflow ID
        default_wf_id = (
            session.current_workflow_id
            if session.current_workflow_id
            else workflows[0].get("workflow_id", "")
        )

        console.print_info("Type or use Tab to select a workflow ID:")

        while True:
            try:
                selected_workflow_id = await prompt_session.prompt_async(
                    "Select workflow: ", default=default_wf_id
                )

                # Strip whitespace
                selected_workflow_id = selected_workflow_id.strip()

                if not selected_workflow_id:
                    console.print_error("Workflow ID cannot be empty.")
                    continue

                # Check if workflow exists in list
                workflow_exists = any(
                    wf.get("workflow_id") == selected_workflow_id for wf in workflows
                )
                if not workflow_exists:
                    console.print_error(
                        f"Workflow '{selected_workflow_id}' not found in running workflows."
                    )
                    console.print_dim("Hint: Use Tab to see available workflows")
                    continue

                if selected_workflow_id == session.current_workflow_id:
                    console.print_info("Already on this workflow.")
                    return CommandResult()

                # Verify the workflow is accessible
                try:
                    status = await get_workflow_status(client, selected_workflow_id)
                    console.print_success(
                        f"✓ Switched to workflow: {selected_workflow_id}"
                    )
                    console.print_dim(f"Current state: {status.state}")
                    return CommandResult(
                        should_switch=True, workflow_id=selected_workflow_id
                    )
                except Exception as e:
                    console.print_error(f"Failed to switch to workflow: {e}")
                    return CommandResult()

            except KeyboardInterrupt:
                console.print_warning("Selection cancelled.")
                return CommandResult()
            except EOFError:
                console.print_warning("Selection cancelled.")
                return CommandResult()
