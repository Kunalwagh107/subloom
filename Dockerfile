# syntax=docker/dockerfile:1
# Headless backend tests only. Windows GUI installers are built on Windows.
FROM python:3.12.10-slim-bookworm AS whisper-build
ARG WHISPER_COMMIT=2eeeba56e9edd762b4b38467bab96c2517163158
ARG WHISPER_SHA256=089b898aa83b24a8321e0fd554eeb0967fb03dd687e27f6374c72d3363b5b429
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates cmake curl g++ make \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /build
RUN curl --fail --location --retry 3 \
      "https://codeload.github.com/ggml-org/whisper.cpp/tar.gz/${WHISPER_COMMIT}" -o whisper.tar.gz \
    && echo "${WHISPER_SHA256}  whisper.tar.gz" | sha256sum --check - \
    && mkdir source && tar -xzf whisper.tar.gz -C source --strip-components=1 \
    && cmake -S source -B output -DCMAKE_BUILD_TYPE=Release \
      -DBUILD_SHARED_LIBS=OFF -DGGML_NATIVE=OFF -DGGML_CUDA=OFF \
      -DGGML_SSE42=OFF -DGGML_AVX=OFF -DGGML_AVX2=OFF -DGGML_FMA=OFF -DGGML_F16C=OFF \
      -DWHISPER_BUILD_TESTS=OFF -DWHISPER_BUILD_EXAMPLES=ON -DWHISPER_CURL=OFF \
    && cmake --build output --target whisper-cli --parallel 2

FROM python:3.12.10-slim-bookworm AS tests
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    QT_QPA_PLATFORM=offscreen \
    SUBLOOM_DATA_DIR=/tmp/subloom-data
RUN apt-get update && apt-get install -y --no-install-recommends \
      ffmpeg fonts-dejavu-core fonts-noto-core libdbus-1-3 libegl1 \
      libglib2.0-0 libgomp1 libopengl0 libpulse0 libx11-xcb1 libxcb-cursor0 libxkbcommon0 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 subloom
COPY --from=whisper-build /build/output/bin/whisper-cli /usr/local/bin/whisper-cli
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/
RUN python -m pip install --upgrade pip==26.2.1 \
    && python -m pip install . pytest==8.3.5 pytest-qt==4.4.0 pysubs2==1.8.0
COPY tests/ ./tests/
COPY scripts/ ./scripts/
USER subloom
CMD ["python", "-m", "pytest", "-q", "-m", "not gui and not asr", "--basetemp=/tmp/subloom-tests", "-o", "cache_dir=/tmp/pytest-cache"]
