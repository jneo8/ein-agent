# Ein Agent CLI

The `ein-agent-cli` is a command-line interface for the Ein Agent system, enabling users to interact with Alertmanager and trigger incident correlation workflows within Temporal.

## Features

-   Query Alertmanager for active alerts.
-   Filter alerts by various criteria (e.g., name, fingerprint, status, blacklist/whitelist).
-   Trigger AI-powered incident correlation workflows in a Temporal cluster.

## Installation

Assuming you have `uv` installed:

```bash
cd ein-agent-cli
uv sync
```

## Usage

The primary command is `run-incident-workflow`, which queries Alertmanager and triggers an incident correlation workflow.

To run the CLI from the `ein-agent-cli` directory:

```bash
uv run python -m ein_agent_cli [OPTIONS]
```

### Filtering Alerts

Filter alerts by name or fingerprint:

```bash
# Include only specific alerts by name
uv run python -m ein_agent_cli -i KubePodNotReady -i KubePodCrashLooping

# Include specific alerts by fingerprint
uv run python -m ein_agent_cli -i 07d5a192e71c

# Mix alert names and fingerprints
uv run python -m ein_agent_cli -i KubePodNotReady -i 07d5a192e71c

# Custom blacklist (exclude specific alerts)
uv run python -m ein_agent_cli -b TargetDown -b Watchdog
```

### Filtering by Status

```bash
# Only firing alerts (default)
uv run python -m ein_agent_cli --status firing

# Only resolved alerts
uv run python -m ein_agent_cli --status resolved

# All alerts regardless of status
uv run python -m ein_agent_cli --status all
```

### Display Options

```bash
# Show full labels in the alert table
uv run python -m ein_agent_cli --show-labels
```

### Configuration

Configure Temporal connection:

```bash
# Set Temporal host, namespace, and queue
uv run python -m ein_agent_cli \
    --temporal-host localhost:7233 \
    --temporal-namespace default \
    --temporal-queue ein-agent-queue
```

Configure MCP servers to use:

```bash
# Specify MCP servers (default: kubernetes, grafana)
uv run python -m ein_agent_cli \
    -m kubernetes \
    -m grafana \
    -m prometheus
```

### Complete Example

```bash
# Query Alertmanager, filter alerts, review, and trigger workflow
uv run python -m ein_agent_cli \
    -a http://10.100.100.12/cos-alertmanager \
    --temporal-host temporal-k8s.temporal.svc.cluster.local:7233 \
    --temporal-namespace default \
    --status firing \
    -i KubePodNotReady \
    -i KubePodCrashLooping \
    -b Watchdog \
    -m kubernetes \
    -m grafana \
    --show-labels

# Automated workflow trigger (no confirmation prompt)
uv run python -m ein_agent_cli \
    -a http://10.100.100.12/cos-alertmanager \
    --temporal-host temporal-k8s.temporal.svc.cluster.local:7233 \
    -i KubePodNotReady \
    -y
```

### Getting Help

```bash
# Show all available options
uv run python -m ein_agent_cli --help
```
