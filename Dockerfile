FROM python:3.14-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/

ENV PYTHONPATH=/app/src

EXPOSE 8001

CMD ["python", "-m", "chatwoot_bridge.cli", "serve"]
