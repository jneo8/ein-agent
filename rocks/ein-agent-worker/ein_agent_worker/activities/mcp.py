"""MCP-related activities."""

import os
from typing import List

from temporalio import activity


@activity.defn
async def get_available_mcp_servers() -> List[str]:
    """Activity to get list of available MCP servers from worker configuration.

    Returns:
        List of MCP server names configured on the worker
    """
    mcp_servers_env = os.getenv("MCP_SERVERS", "")
    if mcp_servers_env:
        return [s.strip() for s in mcp_servers_env.split(",") if s.strip()]
    return []
