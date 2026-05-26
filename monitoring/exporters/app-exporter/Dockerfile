FROM python:3.12-slim

RUN groupadd -r exporter && useradd -r -g exporter exporter

WORKDIR /app
RUN pip install --no-cache-dir prometheus-client==0.20.0

COPY exporter.py .

ENV PYTHONUNBUFFERED=1 \
    EXPORTER_PORT=9090 \
    SCRAPE_INTERVAL=15

USER exporter

EXPOSE 9090

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:9090/health')"

CMD ["python", "exporter.py"]
