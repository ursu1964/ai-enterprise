FROM python:3.12.11-slim-bookworm

ARG REVIEWER_UID=10002
ARG REVIEWER_GID=10002

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/home/reviewer \
    XDG_CACHE_HOME=/workspace/.reviewer/cache \
    TMPDIR=/tmp

RUN groupadd \
      --gid "${REVIEWER_GID}" \
      reviewer \
    && useradd \
      --uid "${REVIEWER_UID}" \
      --gid "${REVIEWER_GID}" \
      --create-home \
      --shell /usr/sbin/nologin \
      reviewer \
    && apt-get update \
    && apt-get install --yes --no-install-recommends \
      bash \
      ca-certificates \
      git \
      nodejs \
      npm \
      patch \
    && rm -rf /var/lib/apt/lists/* \
    && python -m pip install --upgrade pip \
    && python -m pip install pytest==8.3.4

COPY docker/review-agent/runner/review.py /opt/reviewer/review.py
COPY docker/review-agent/entrypoint.sh /opt/reviewer/entrypoint.sh

RUN chmod 0555 \
      /opt/reviewer/review.py \
      /opt/reviewer/entrypoint.sh

USER reviewer:reviewer
WORKDIR /workspace

ENTRYPOINT ["/opt/reviewer/entrypoint.sh"]
