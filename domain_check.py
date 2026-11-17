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

行为 (无论成功或失败都会通过青龙自带的 notify.py 通知):
  - 剩余 > 120 天: 检查正常, 推送"检查正常"通知, exit 0
  - 剩余 <= 120 天 (进入免费续费窗口): 推送续费提醒, exit 1
    (青龙一天跑一次, 窗口期内每天都提醒, 直到续费后剩余天数回到 120 天以上)
  - 已过期: 推送紧急提醒, exit 1
  - 运行失败 (key 缺失/接口异常/列表为空): 推送失败提醒, exit 1

环境变量 (青龙 -> 环境变量):
  DP_API_KEY        必填, dp_live_ 开头的 API key
  DP_BASE_URL       可选, 默认 https://domain-api.digitalplat.org/api/v1
  DP_DOMAINS        可选, 逗号分隔, 只监控列出的域名 (默认: 账户内全部免费域名)
  RENEW_WINDOW_DAYS 可选, 免费续费窗口天数, 默认 120
  通知渠道           直接调用青龙自带的 notify.py (面板内置, 无需上传),
                     在青龙环境变量/系统设置中配置渠道 key 即可 (如 PUSH_KEY=server酱)
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
TIMEOUT = 30
DASH_URL = "https://dashboard.digitalplat.org"

# ---------------- 统一通知模块加载 ----------------
# 直接调用青龙自带的 notify.py（面板内置在脚本目录，无需在仓库中自带）。
# 青龙任务的工作目录就是脚本目录，因此 from notify import send 会命中青龙的 notify.py。
hadsend = False
send = None
try:
    from notify import send
    hadsend = True
    print("✅ 已加载青龙内置 notify.py 通知模块")
except ImportError:
    print("⚠️ 未找到 notify.py 通知模块，跳过通知功能（不影响域名检查）")
NOTIFY_OK = hadsend


def notify(title, content):
    """通过青龙 notify.py 发送通知; 通知模块不可用时仅记日志, 不影响主流程。"""
    if not NOTIFY_OK:
        log("WARNING: 通知模块不可用, 未发送通知: %s" % title)
        return
    try:
        send(title, content)
    except Exception as e:
        log("ERROR: 通知发送失败 %s: %s" % (title, e))


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


def parse_date(s):
    return datetime.datetime.strptime(s, "%Y%m%d").date()


def main():
    if not API_KEY:
        msg = "未设置 DP_API_KEY 环境变量"
        log("ERROR: %s" % msg)
        notify("❌ DigitalPlat 域名检查失败", msg)
        sys.exit(1)

    code, data = api_get("/domains")
    if code != 200:
        msg = "拉取域名列表失败 HTTP %s: %s" % (code, json.dumps(data, ensure_ascii=False)[:300])
        log("ERROR: %s" % msg)
        notify("❌ DigitalPlat 域名检查失败", msg)
        sys.exit(1)

    domains = data.get("data", [])
    if not domains:
        msg = "域名列表为空, 请检查 key 权限"
        log("WARNING: %s" % msg)
        notify("❌ DigitalPlat 域名检查失败", msg)
        sys.exit(1)

    today = datetime.date.today()
    alerts = []
    status_lines = []
    checked = 0

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
        checked += 1
        line = "%s: 到期 %s, 剩余 %s 天 (slot=%s)" % (name, expires, days_left, slot)
        status_lines.append(line)
        log(line)

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

        # 窗口期内: 每天提醒续费 (青龙一天跑一次, 一旦 <= 窗口天数就提醒)
        alerts.append(
            "⏰ %s 免费续费窗口开启/临近 (到期 %s, 剩余 %s 天)\n"
            "   需要你做 (免费, 无需支付, 有效期内点一次即可):\n"
            "   登录 %s -> 域名 -> %s -> [续费] 页 -> 点「申请免费续费」"
            % (name, expires, days_left, DASH_URL, name))

    if alerts:
        for a in alerts:
            log(a)
        content = "\n\n".join(alerts)
        if status_lines:
            content += "\n\n--- 当前状态 ---\n" + "\n".join(status_lines)
        notify("⚠️ DigitalPlat 域名到期提醒", content)
        sys.exit(1)

    log("检查完成, 共 %s 个域名, 全部正常" % checked)
    notify("✅ DigitalPlat 域名检查正常",
           "共检查 %s 个域名:\n\n%s" % (checked, "\n".join(status_lines) if status_lines else "(无匹配域名)"))
    sys.exit(0)


if __name__ == "__main__":
    main()
