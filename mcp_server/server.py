"""
mcp_server/server.py
FastMCP server for Wayfind ("wayfind").
Registers all 6 core domain tools with FastMCP.
"""

from __future__ import annotations

import logging

from fastmcp import FastMCP

from mcp_server.tools.get_case_status import get_case_status
from mcp_server.tools.get_guidance import get_guidance
from mcp_server.tools.image_match_candidates import image_match_candidates
from mcp_server.tools.search_child_records import search_child_records
from mcp_server.tools.search_support import search_support
from mcp_server.tools.submit_found_child_report import submit_found_child_report

logger = logging.getLogger(__name__)

# Create FastMCP server instance
mcp = FastMCP("wayfind")

# Register all 6 domain tools
mcp.tool()(search_child_records)
mcp.tool()(image_match_candidates)
mcp.tool()(submit_found_child_report)
mcp.tool()(search_support)
mcp.tool()(get_guidance)
mcp.tool()(get_case_status)

logger.info("FastMCP server 'wayfind' initialised with 6 registered tools")
