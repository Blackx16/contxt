FROM python:3.12-slim
WORKDIR /app
COPY server/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY gateway/ ./gateway/
COPY server/ ./server/
CMD ["python", "-m", "server.mcp_server"]
