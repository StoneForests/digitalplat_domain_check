# DigitalPlat 域名到期监控

监控 **dpdns.org（DigitalPlat）免费域名** 的到期情况，并在到期窗口临近时通过多种通知渠道提醒你，无论检查成功还是失败都会推送通知。部署到**青龙面板**，建议每天跑一次。

## 脚本组成

| 文件 | 作用 |
| --- | --- |
| `domain_check.py` | 唯一脚本：调用 DigitalPlat 公共 API 拉取域名列表，计算剩余天数，剩余 ≤ 120 天时每天提醒续费，并在成功/失败时发送通知 |

> 通知功能直接复用**青龙面板自带的 `notify.py`**（无需在本仓库中携带）。青龙任务工作目录就是脚本目录，脚本会自动 `from notify import send` 加载它；只要你在青龙里配好了通知 key，本脚本就能直接推送。

## 工作原理

一句话：每天检查免费域名还剩多少天到期，**一旦少于 120 天（进入免费续费窗口）就每天提醒你去续费**；检查成功、到期临近、已过期、运行失败都会通知（成功 `exit 0`，需关注或失败 `exit 1`）。

> 免费续费只能在 dashboard 浏览器页面点「申请免费续费」完成（免费、无需支付，窗口期 120 天内任意时间点均可），收到提醒后手动处理即可。

## 青龙面板部署

1. 上传 `domain_check.py`（放到青龙脚本目录，如 `/ql/scripts/` 的任一位置即可）
2. 在青龙面板 **环境变量** 中配置下述 key
3. 新建定时任务：命令 `python3 domain_check.py`，定时规则建议 `0 9 * * *`（每天 9 点）

### 需要配置的 key（脚本本身）

| 环境变量 | 必填 | 作用 |
| --- | --- | --- |
| `DP_API_KEY` | ✅ 必填 | DigitalPlat 的 API key，`dp_live_` 开头，在 dpdns.org 控制台获取 |
| `DP_BASE_URL` | 可选 | API 基地址，默认 `https://domain-api.digitalplat.org/api/v1` |
| `DP_DOMAINS` | 可选 | 逗号分隔，只监控列出的域名；不填则监控账户内全部免费域名 |
| `RENEW_WINDOW_DAYS` | 可选 | 免费续费窗口天数，默认 `120` |

### 需要配置的 key（通知渠道，青龙自带 notify.py 支持）

> 任选至少一个渠道启用即可。设置了哪些 key，通知就会走哪些渠道（会同时推送到所有已启用的渠道）。下面按渠道分组列出每个 key 的作用。

**Server酱 / Bark / PushDeer / PushMe**

| 环境变量 | 作用 |
| --- | --- |
| `PUSH_KEY` | Server酱的 SendKey，兼容旧版与 Turbo 版，`SCT` 开头走新版接口（推荐，微信直达） |
| `BARK_PUSH` | Bark 的 IP 或设备码，形如 `https://api.day.app/DxHcxxxxxRxxxxxxcm/` |
| `BARK_ARCHIVE` | Bark 推送是否存档 |
| `BARK_GROUP` | Bark 推送分组 |
| `BARK_SOUND` | Bark 推送声音 |
| `BARK_ICON` | Bark 推送图标 |
| `BARK_LEVEL` | Bark 推送时效性 |
| `BARK_URL` | Bark 推送跳转 URL |
| `DEER_KEY` | PushDeer 的 pushkey |
| `DEER_URL` | PushDeer 自建服务地址（可选，默认官方 `api2.pushdeer.com`） |
| `PUSHME_KEY` | PushMe 酱的 push_key |

**钉钉 / 飞书 / 企业微信**

| 环境变量 | 作用 |
| --- | --- |
| `DD_BOT_TOKEN` | 钉钉机器人 access_token |
| `DD_BOT_SECRET` | 钉钉机器人加签密钥（开启加签时必填） |
| `FSKEY` | 飞书机器人 webhook 的 key |
| `QYWX_AM` | 企业微信应用推送参数，逗号分隔：`corpid,corpsecret,touser,agentid[,media_id]` |
| `QYWX_KEY` | 企业微信机器人 webhook key |
| `QYWX_ORIGIN` | 企业微信代理地址（可选） |

**Telegram / QQ**

| 环境变量 | 作用 |
| --- | --- |
| `TG_BOT_TOKEN` | Telegram 机器人 token，形如 `1407203283:AAG...` |
| `TG_USER_ID` | Telegram 接收者 user id |
| `TG_API_HOST` | Telegram 代理 API 地址（可选） |
| `TG_PROXY_HOST` / `TG_PROXY_PORT` / `TG_PROXY_AUTH` | Telegram 代理配置（可选） |
| `QMSG_KEY` | qmsg 酱的 key |
| `QMSG_TYPE` | qmsg 酱发送类型（`send` 或 `group`） |
| `GOBOT_URL` | go-cqhttp 推送地址，如 `http://127.0.0.1/send_private_msg` |
| `GOBOT_QQ` | go-cqhttp 推送的群或用户（`user_id=` / `group_id=`） |
| `GOBOT_TOKEN` | go-cqhttp 的 access_token（可选） |
| `CHRONOCAT_URL` / `CHRONOCAT_QQ` / `CHRONOCAT_TOKEN` | Chronocat（QQ 机器人）的地址 / 推送对象 / token |

**其他**

| 环境变量 | 作用 |
| --- | --- |
| `IGOT_PUSH_KEY` | iGot 聚合推送的 key |
| `GOTIFY_URL` / `GOTIFY_TOKEN` / `GOTIFY_PRIORITY` | Gotify 的地址 / token / 优先级 |
| `CHAT_URL` / `CHAT_TOKEN` | Synology Chat 的地址和 token |
| `PUSH_PLUS_TOKEN` / `PUSH_PLUS_USER` | PushPlus 微信推送的用户令牌 / 群组编码 |
| `AIBOTK_KEY` / `AIBOTK_TYPE` / `AIBOTK_NAME` | 智能微秘书的 apikey / 发送目标类型（room|contact）/ 群名或昵称 |
| `SMTP_SERVER` | SMTP 邮件服务器，形如 `smtp.exmail.qq.com:465` |
| `SMTP_SSL` | SMTP 是否使用 SSL，`true` 或 `false` |
| `SMTP_EMAIL` / `SMTP_PASSWORD` / `SMTP_NAME` | SMTP 收发件邮箱 / 密码或授权码 / 发件人姓名 |
| `WEBHOOK_URL` | 自定义通知请求地址（请求头或请求体中须含 `$title` 和 `$content` 占位符） |
| `WEBHOOK_METHOD` | 自定义通知请求方法（POST / GET） |
| `WEBHOOK_BODY` / `WEBHOOK_HEADERS` / `WEBHOOK_CONTENT_TYPE` | 自定义通知请求体 / 请求头 / content-type |
| `HITOKOTO` | 是否在通知末尾附带一言（`true`/`false`，默认关闭） |
| `SKIP_PUSH_TITLE` | 按标题跳过某些推送，多个标题用回车分隔 |
| `CONSOLE` | 是否在控制台输出通知内容，默认 `true` |

## 最小配置示例（只用 Server酱）

```
DP_API_KEY = dp_live_xxxxxxxxxxxxxxxx
PUSH_KEY = SCTxxxxxxxxxxxxxxxxxx
```

配置完成后，保存并运行任务即可。每次运行无论成功失败都会收到 Server酱 推送。

## 常见问题

- **收不到通知？** 检查是否至少配置了一个通知渠道的 key（如 `PUSH_KEY`），并确认青龙面板的系统设置里已开启对应渠道；`notify.py` 由青龙自带，无需上传。
- **为什么窗口期内每天都收到提醒？** 这是有意设计：脚本一天跑一次，剩余天数一旦 ≤ 120 天每天都会提醒，直到你续费后剩余天数恢复到 120 天以上才停止，避免漏掉。
- **想同时用多个渠道？** 直接配置多个通知渠道的 key 即可，会同时推送。

