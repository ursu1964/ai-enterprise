#!/usr/bin/env bash
set -Eeuo pipefail

umask 022

exec python /opt/runtime/run.py
