FROM python:3.12-slim-bookworm

ARG RUNTIME_UID=10001
ARG RUNTIME_GID=10001

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/home/runtime \
    XDG_CACHE_HOME=/workspace/.runtime/cache \
    TMPDIR=/tmp

RUN groupadd \
      --gid "${RUNTIME_GID}" \
      runtime \
    && useradd \
      --uid "${RUNTIME_UID}" \
      --gid "${RUNTIME_GID}" \
      --create-home \
      --shell /usr/sbin/nologin \
      runtime \
    && apt-get update \
    && apt-get install --yes --no-install-recommends \
      bash \
      ca-certificates \
      git \
      patch \
    && rm -rf /var/lib/apt/lists/* \
    && python -m pip install --upgrade pip \
    && python -m pip install pytest==8.3.4

COPY docker/execution-agent/runner/run.py /opt/runtime/run.py
COPY docker/execution-agent/runner/apply_edits.py /opt/runtime/apply_edits.py
COPY docker/execution-agent/entrypoint.sh /opt/runtime/entrypoint.sh

RUN chmod 0555 \
      /opt/runtime/run.py \
      /opt/runtime/apply_edits.py \
      /opt/runtime/entrypoint.sh

USER runtime:runtime
WORKDIR /workspace

ENTRYPOINT ["/opt/runtime/entrypoint.sh"]
