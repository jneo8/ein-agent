"""Implementation of the /import-alerts slash command."""
from typing import Any, Dict, List

from prompt_toolkit import PromptSession
from rich.table import Table
from temporalio.client import Client as TemporalClient

from ein_agent_cli import console
from ein_agent_cli.alertmanager import query_alertmanager
from ein_agent_cli.models import (
    AlertmanagerQueryParams,
    ContextItem,
    ContextItemType,
    HumanInLoopConfig,
    SessionState,
    WorkflowAlert,
)
from ein_agent_cli.slash_commands.base import CommandResult, SlashCommand


class ImportAlertsCommand(SlashCommand):
    """Import alerts from AlertManager to local context."""

    @property
    def name(self) -> str:
        return "import-alerts"

    @property
    def description(self) -> str:
        return "Query AlertManager and import alerts to local context"

    async def execute(
        self, args: str, config: HumanInLoopConfig, client: TemporalClient, session: SessionState
    ) -> CommandResult:
        import_args = self._parse_args(args)
        alertmanager_url = (
            import_args.get("url")
            or config.alertmanager_url
            or "http://localhost:9093"
        )

        console.print_info(f"Querying AlertManager at {alertmanager_url}...")
        try:
            all_alerts = await query_alertmanager(
                AlertmanagerQueryParams(url=alertmanager_url)
            )
            if not all_alerts:
                console.print_info("No alerts found.")
                return CommandResult()

            await self._interactive_import_loop(
                all_alerts, import_args, alertmanager_url, session
            )
        except Exception as e:
            console.print_error(f"Failed to import alerts: {e}")
        return CommandResult()

    async def _interactive_import_loop(
        self, all_alerts, import_args, alertmanager_url, session
    ):
        selected_indices = set()
        while True:
            context_alerts = session.local_context.get_items_by_type(
                ContextItemType.ALERT
            )
            if context_alerts:
                self._display_context_alerts_table(context_alerts)

            context_fingerprints = {item.item_id for item in context_alerts}
            new_alerts = [
                a for a in all_alerts if a.fingerprint not in context_fingerprints
            ]
            filtered_alerts = self._filter_alerts(new_alerts, import_args)

            if not filtered_alerts:
                console.print_info("No new alerts matched the filters.")
                if any(v is not None for k, v in import_args.items() if k != "status"):
                    if await self._prompt_for_clear_filters():
                        import_args = self._parse_args("")
                        continue
                return

            self._display_alerts_table(filtered_alerts, selected_indices)
            action = await self._prompt_for_action()
            if not action:
                continue

            cmd, *args = action.lower().split()
            if cmd == "i":
                if not selected_indices:
                    console.print_warning(
                        "No alerts selected. Use 's' to select first."
                    )
                    continue
                to_import = [filtered_alerts[i] for i in sorted(selected_indices)]
                self._import_alerts(to_import, alertmanager_url, session)
                all_alerts = [
                    a for a in all_alerts if a.fingerprint not in {al.fingerprint for al in to_import}
                ]
                selected_indices.clear()
            elif cmd == "a":
                self._import_alerts(filtered_alerts, alertmanager_url, session)
                all_alerts = [
                    a for a in all_alerts if a.fingerprint not in {al.fingerprint for al in filtered_alerts}
                ]
                selected_indices.clear()
            elif cmd == "s" and args:
                self._handle_selection(args[0], filtered_alerts, selected_indices)
            elif cmd == "f":
                import_args.update(await self._prompt_for_filters())
                selected_indices.clear()
            elif cmd == "c":
                import_args = self._parse_args("")
                selected_indices.clear()
                console.print_info("Filters cleared.")
            elif cmd == "q":
                break

    def _filter_alerts(self, alerts, filters):
        # Existing filter logic...
        return alerts  # Placeholder

    def _display_context_alerts_table(self, alerts: List[ContextItem]):
        table = Table(
            title="Alerts in Local Context", show_header=True, header_style="bold blue"
        )
        # Define columns...
        for alert_item in alerts:
            # Populate rows...
            pass
        console.print_table(table)
        console.print_newline()

    def _display_alerts_table(self, alerts: List[Any], selected_indices: set):
        table = Table(
            title="New Alerts from AlertManager",
            show_header=True,
            header_style="bold magenta",
        )
        # Define columns...
        for idx, alert in enumerate(alerts, 1):
            # Populate rows...
            pass
        console.print_table(table)

    async def _prompt_for_action(self):
        console.print_info(
            "Actions: (s)elect, (i)mport, (a)ll, (f)ilter, (c)lear filter, (q)uit"
        )
        return await PromptSession().prompt_async("Action: ")

    async def _prompt_for_filters(self):
        # Existing filter prompt logic...
        return {}

    async def _prompt_for_clear_filters(self) -> bool:
        return (
            await PromptSession().prompt_async(
                "No results. Clear all filters and try again? (y/n): "
            )
        ).lower() == "y"

    def _handle_selection(self, selection_str, alerts, selected_indices):
        # Existing selection logic...
        pass

    def _import_alerts(self, alerts_to_import, alertmanager_url, session):
        for alert in alerts_to_import:
            item = ContextItem(
                item_id=alert.fingerprint,
                item_type=ContextItemType.ALERT,
                data=WorkflowAlert.from_alertmanager_alert(alert).model_dump(),
                source=alertmanager_url,
            )
            session.local_context.add_item(item)
        console.print_success(f"Imported {len(alerts_to_import)} alert(s).")

    def _parse_args(self, args: str) -> Dict[str, Any]:
        # Existing argument parsing...
        return {"status": "active"}

