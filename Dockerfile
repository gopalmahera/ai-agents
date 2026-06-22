FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY mcp-servers/ ./mcp-servers/
COPY alert-agent/ ./alert-agent/
COPY start.sh .
RUN chmod +x start.sh

EXPOSE 5001

CMD ["./start.sh"]
