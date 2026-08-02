#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


def _load_signer():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "apps/api/src"))
    from ai_enterprise.infrastructure.security.local_activation import (
        sign_identity_assertion,
    )

    return sign_identity_assertion


def main() -> int:
    parser = argparse.ArgumentParser(description="Create trusted proxy identity headers.")
    parser.add_argument("--secret", required=True)
    parser.add_argument("--actor-id", required=True)
    parser.add_argument("--actor-type", default="human")
    parser.add_argument("--actor-role", default="platform-admin")
    parser.add_argument("--timestamp", type=int, default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    timestamp = args.timestamp or int(time.time())
    signature = _load_signer()(
        secret=args.secret.encode(),
        actor_id=args.actor_id,
        actor_type=args.actor_type,
        actor_role=args.actor_role,
        timestamp=timestamp,
    )
    headers = {
        "X-Actor-ID": args.actor_id,
        "X-Actor-Type": args.actor_type,
        "X-Actor-Role": args.actor_role,
        "X-Proxy-Timestamp": str(timestamp),
        "X-Proxy-Signature": signature,
    }
    if args.json:
        print(json.dumps(headers, sort_keys=True))
    else:
        for key, value in headers.items():
            print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
