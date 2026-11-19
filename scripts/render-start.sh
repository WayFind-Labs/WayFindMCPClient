#!/bin/sh
set -eu

if [ -n "${GATEWAY_HOSTPORT:-}" ]; then
    export POSTGRES_SERVICE_URL="http://${GATEWAY_HOSTPORT}"
fi

case "${1:-}" in
    agent)
        if [ -n "${MCP_HOSTPORT:-}" ]; then
            export MCP_SERVER_URL="http://${MCP_HOSTPORT}/sse"
        fi
        exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-10000}"
        ;;
    mcp)
        export MCP_SERVER_HOST=0.0.0.0
        export MCP_SERVER_PORT="${PORT:-10000}"
        exec python -m mcp_server.server
        ;;
    *)
        echo "Expected agent or mcp" >&2
        exit 2
        ;;
esac
