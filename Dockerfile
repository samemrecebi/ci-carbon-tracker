FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install packages that compile C extensions from source
RUN pip install --no-cache-dir --no-binary :all: \
    numpy==2.2.4 \
    pandas==2.2.3 \
    pyyaml==6.0.2 \
    markupsafe==3.0.2 \
    cffi==1.17.1 \
    cryptography==44.0.2

COPY <<'EOF' /app/benchmark.py
print("Carbon tracker CI Docker Test test")
print("Will sleep for 20 seconds now inside the docker build env")
EOF

RUN python /app/benchmark.py

RUN sleep 20

WORKDIR /app
CMD ["python", "benchmark.py"]
