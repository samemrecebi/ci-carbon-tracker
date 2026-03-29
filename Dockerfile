FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    build-essential \
    gfortran \
    pkg-config \
    libffi-dev \
    libssl-dev \
    libyaml-dev \
    libopenblas-dev \
    cargo \
    rustc \
    && rm -rf /var/lib/apt/lists/*

# Build tools needed to compile from source
RUN pip install --no-cache-dir \
    meson meson-python cython numpy-base setuptools wheel

# Install packages from source — specify each individually so their
# build-time dependencies (meson, ninja, etc.) can use pre-built wheels.
RUN pip install --no-cache-dir \
    --no-binary numpy,pandas,pyyaml,markupsafe,cffi,cryptography \
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
