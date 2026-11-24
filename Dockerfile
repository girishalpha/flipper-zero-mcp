# Container image for Flipper Zero MCP Server (Glama introspection & containerized hosts)
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy server package and entrypoint
COPY flipper_mcp/ ./flipper_mcp/
COPY flipper_mcp_server.py README.md LICENSE ./

ENV PYTHONUNBUFFERED=1

# MCP stdio interface
CMD ["python", "-m", "flipper_mcp"]
