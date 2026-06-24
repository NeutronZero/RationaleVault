from __future__ import annotations

import sys
from mcp.server.fastmcp import FastMCP

# Define the FastMCP server instance
server = FastMCP("rationalevault")

# Import tools so they register on the server
import rationalevault.mcp.tools

def run(transport: str = "stdio", port: int = 8080) -> None:
    """Run the MCP server using the specified transport and port."""
    if transport == "stdio":
        server.run(transport="stdio")
    elif transport == "sse":
        server.run(transport="sse", port=port)
    else:
        print(f"Error: Unknown transport '{transport}'")
        sys.exit(1)
