FROM python:3.12-slim
WORKDIR /app
COPY server/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# The MCP server imports schema.models and gateway.distill at runtime, and seeds
# from schema/fixtures — copy all three or the container runs degraded.
COPY schema/ ./schema/
COPY gateway/ ./gateway/
COPY server/ ./server/

# Serve the HTTP bridge so the container is demoable with zero setup:
#   docker run -p 8787:8787 contxt   →   curl http://127.0.0.1:8787/health
# Mock cloud Gemma by default (runs with no API keys) and bind all interfaces
# inside the container (the host still defaults to loopback when run directly).
ENV CONTXT_BRIDGE_HOST=0.0.0.0 \
    CONTXT_MOCK_GEMMA=1
EXPOSE 8787
CMD ["python", "-m", "server.http_bridge"]

# The stdio MCP server (for Claude Desktop) is still available via:
#   docker run contxt python -m server.mcp_server
