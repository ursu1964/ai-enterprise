FROM python:3.12.11-slim-bookworm@sha256:519591d6871b7bc437060736b9f7456b8731f1499a57e22e6c285135ae657bf7

ARG REVIEWER_UID=10002
ARG REVIEWER_GID=10002
ARG BASH_VERSION=5.2.15-2+b13
ARG CA_CERTIFICATES_VERSION=20230311+deb12u1
ARG GIT_VERSION=1:2.39.5-0+deb12u3
ARG NODEJS_VERSION=18.20.4+dfsg-1~deb12u2
ARG NPM_VERSION=9.2.0~ds1-1
ARG PATCH_VERSION=2.7.6-7

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
      "bash=${BASH_VERSION}" \
      "ca-certificates=${CA_CERTIFICATES_VERSION}" \
      "git=${GIT_VERSION}" \
      "nodejs=${NODEJS_VERSION}" \
      "npm=${NPM_VERSION}" \
      "patch=${PATCH_VERSION}" \
    && rm -rf /var/lib/apt/lists/*

COPY docker/agent-runtime-requirements.txt /opt/reviewer/requirements.txt
COPY docker/review-agent/runner/review.py /opt/reviewer/review.py
COPY docker/review-agent/entrypoint.sh /opt/reviewer/entrypoint.sh

RUN python -m pip install --require-hashes --no-deps -r /opt/reviewer/requirements.txt \
    && chmod 0444 /opt/reviewer/requirements.txt \
    && chmod 0555 \
      /opt/reviewer/review.py \
      /opt/reviewer/entrypoint.sh

USER reviewer:reviewer
WORKDIR /workspace

ENTRYPOINT ["/opt/reviewer/entrypoint.sh"]
