FROM ubuntu:24.04

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        build-essential \
        cmake \
        make \
        ninja-build \
        poppler-utils \
        python3 \
        python3-pip \
        python3-venv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
COPY . .

RUN python3 -m venv /opt/content-factory \
    && /opt/content-factory/bin/python -m pip install --no-cache-dir .

ENV PATH="/opt/content-factory/bin:${PATH}"

CMD ["make", "all"]
