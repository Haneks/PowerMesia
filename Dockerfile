# PowerPoint Paroissial - Streamlit app
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (config, tools, context, app)
COPY args/ args/
COPY context/ context/
COPY hardprompts/ hardprompts/
COPY orchestration/ orchestration/
COPY tools/ tools/
COPY app.py .

# Optional: create mount points for data and output (run as non-root if needed)
ENV DATA_DIR=/data
ENV OUTPUT_DIR=/output
RUN mkdir -p /data /output

# Streamlit: bind to 0.0.0.0 so container is reachable from host
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_HEADLESS=true

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.port=8501"]
