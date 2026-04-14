FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV LD_LIBRARY_PATH=/usr/local/lib:${LD_LIBRARY_PATH}

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    cmake \
    git \
    libssl-dev \
    ninja-build \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt

RUN git clone --depth 1 https://github.com/open-quantum-safe/liboqs.git

RUN cmake -S /opt/liboqs -B /opt/liboqs/build \
    -GNinja \
    -DCMAKE_BUILD_TYPE=Release \
    -DBUILD_SHARED_LIBS=ON \
    -DOQS_BUILD_ONLY_LIB=ON \
    && cmake --build /opt/liboqs/build \
    && cmake --install /opt/liboqs/build \
    && ldconfig

WORKDIR /workspace

COPY requirements.txt /workspace/requirements.txt
RUN python -m pip install --upgrade pip && \
    python -m pip install -r /workspace/requirements.txt

COPY . /workspace

RUN python /workspace/verify_oqs.py

CMD ["python", "main.py", "--help"]
