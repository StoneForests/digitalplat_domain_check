#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DigitalPlat (dpdns.org) 免费域名到期监控 + 分档提醒
部署到青龙面板，建议每天跑一次。

背景 (2026-11-12 实测):
  - 免费续一年只能在 dashboard 浏览器页面操作 (panel API 被 Cloudflare 限制, 仅浏览器可达)
  - 公共 API (domain-api.digitalplat.org) 可任意机器直连, 但只有查询, 无 operated 域名续费接口
  => 本脚本负责监控与提醒; 续费由你收到通知后到 dashboard 点一下"申请免费续费"完成
     (免费、无需支付, 窗口期 120 天内任意时间点均可, 不紧急)

行为:
  - 剩余 > 120 天: 只记日志, exit 0 (静默)
  - 进入窗口后首次到达检查点 (120/90/60/30/14/7/3/1 天): 输出提醒, exit 1
    (青龙任务配置"失败通知"即可收到推送; 无检查点的日子保持静默, 不刷屏)
  - 已过期: exit 1 紧急提醒

环境变量 (青龙 -> 环境变量):
  DP_API_KEY        必填, dp_live_ 开头的 API key
  DP_BASE_URL       可选, 默认 https://domain-api.digitalplat.org/api/v1
  DP_DOMAINS        可选, 逗号分隔, 只监控列出的域名 (默认: 账户内全部免费域名)
  RENEW_WINDOW_DAYS 可选, 免费续费窗口天数, 默认 120
"""
import datetime
import json
import os
import sys

import requests

BASE_URL = os.environ.get("DP_BASE_URL", "https://domain-api.digitalplat.org/api/v1").rstrip("/")
API_KEY = os.environ.get("DP_API_KEY", "").strip()
WINDOW = int(os.environ.get("RENEW_WINDOW_DAYS", "120"))
ONLY_DOMAINS = [d.strip().lower() for d in os.environ.get("DP_DOMAINS", "").split(",") if d.strip()]
CHECKPOINTS = [120, 90, 60, 30, 14, 7, 3, 1]
TIMEOUT = 30
DASH_URL = "https://dashboard.digitalplat.org"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(SCRIPT_DIR, ".dpdns_watch_state.json")


def log(msg):
    print("[dpdns] %s %s" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg), flush=True)


def api_get(path):
    headers = {"Authorization": "Bearer %s" % API_KEY, "Accept": "application/json"}
    r = requests.get(BASE_URL + path, headers=headers, timeout=TIMEOUT)
    try:
        data = r.json()
    except ValueError:
        data = {"raw": r.text[:500]}
    return r.status_code, data


def load_state():
    try:
        with open(STATE_FILE) as f:
            st = json.load(f)
        st.setdefault("fired", {})
        return st
    except Exception:
        return {"fired": {}}


def save_state(st):
    with open(STATE_FILE, "w") as f:
        json.dump(st, f, ensure_ascii=False)


def parse_date(s):
    return datetime.datetime.strptime(s, "%Y%m%d").date()


def main():
    if not API_KEY:
        log("ERROR: 未设置 DP_API_KEY 环境变量")
        sys.exit(1)

    code, data = api_get("/domains")
    if code != 200:
        log("ERROR: 拉取域名列表失败 HTTP %s: %s" % (code, json.dumps(data, ensure_ascii=False)[:300]))
        sys.exit(1)

    domains = data.get("data", [])
    if not domains:
        log("WARNING: 域名列表为空, 请检查 key 权限")
        sys.exit(1)

    today = datetime.date.today()
    st = load_state()
    checkpoints = sorted({WINDOW} | {c for c in CHECKPOINTS if c < WINDOW}, reverse=True)
    alerts = []

    for d in domains:
        name = d.get("domain", "")
        slot = d.get("slot_type")
        if ONLY_DOMAINS and name.lower() not in ONLY_DOMAINS:
            continue
        try:
            expires = parse_date(d.get("expires_at", ""))
        except Exception:
            log("跳过 %s: 无法解析到期日 %r" % (name, d.get("expires_at")))
            continue
        days_left = (expires - today).days
        log("%s: 到期 %s, 剩余 %s 天 (slot=%s)" % (name, expires, days_left, slot))

        if days_left <= 0:
            alerts.append(
                "!!! %s 已于 %s 到期, 域名有被回收风险! 立即登录 %s/domains/%s 处理!"
                % (name, expires, DASH_URL, name))
            continue

        if slot != "free" and not ONLY_DOMAINS:
            log("跳过 %s: slot_type=%s 非免费, 且未通过 DP_DOMAINS 显式指定" % (name, slot))
            continue

        if days_left > WINDOW:
            log("尚未进入窗口 (剩余 > %s 天), 无需提醒" % WINDOW)
            continue

        # 窗口期内: 检查到达但未发过的提醒点 (含部署滞后一次性补发)
        key = "%s@%s" % (name, d.get("expires_at"))
        fired = st["fired"].get(key, [])
        due = [c for c in checkpoints if days_left <= c and c not in fired]
        if due:
            fired.extend(sorted(due, reverse=True))
            st["fired"][key] = fired
            save_state(st)
            alerts.append(
                "⏰ %s 免费续费窗口开启/临近 (到期 %s, 剩余 %s 天, 已过检查点: %s)\n"
                "   需要你做 (免费, 无需支付, 有效期内点一次即可):\n"
                "   登录 %s -> 域名 -> %s -> [续费] 页 -> 点「申请免费续费」"
                % (name, expires, days_left, "/".join(str(c) for c in sorted(due, reverse=True)),
                   DASH_URL, name))
            continue
        log("窗口期内, 等待续费, 本检查点已提醒过, 保持静默")

    if alerts:
        for a in alerts:
            log(a)
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
