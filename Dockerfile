FROM debian:bookworm-slim@sha256:7c7b2c966bc9ee8cedfeef67e0e279108992c77681fa595db4a9d65c06ccc587
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-yaml dnsmasq-base iproute2 iputils-ping ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY app/ /app/
COPY scripts/dhcp.py /app/dhcp.py
ENV PYTHONUNBUFFERED=1 NDF_DATA_ROOT=/data
EXPOSE 9080
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s CMD python3 -c "import json,os; from urllib.request import urlopen; p=json.load(open(os.environ.get('NDF_DATA_ROOT','/data')+'/control-center/settings.json'))['panel_port']; urlopen('http://127.0.0.1:'+str(p)+'/health',timeout=3)" || exit 1
CMD ["python3", "/app/server.py"]
