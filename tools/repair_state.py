#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验并修复 renewal_state.json，供工作流闸门步骤调用（仅标准库）。"""

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

STATE_FILE = Path("renewal_state.json")


def main() -> int:
    if not STATE_FILE.exists():
        print("missing")
        return 0

    raw = STATE_FILE.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("state root is not an object")
        if not isinstance(data.get("next_renewal_date", ""), str):
            raise ValueError("next_renewal_date is not a string")
        if data.get("status") not in (None, "waiting", "stopped"):
            raise ValueError("unexpected status value")
    except Exception:
        backup = STATE_FILE.with_name(
            f"renewal_state.broken-{datetime.now(timezone.utc):%Y%m%d%H%M%S}.json"
        )
        shutil.copy2(STATE_FILE, backup)
        print(f"backed up corrupted content to {backup.name}: {raw.strip()[:200]}")
        repaired = {
            "next_renewal_date": "",
            "status": "waiting",
            "detail": "状态文件损坏，已自动重置；本次运行将按合同页面自愈日期",
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        STATE_FILE.write_text(
            json.dumps(repaired, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print("repaired")
        return 0

    print("ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
