# EUserv 免费 VPS 自动续约 · 完整部署教程

> 本教程面向从未接触过本项目的用户，按步骤从零开始配置一个**完全自动**的 EUserv 免费 VPS 续约系统：到点自动续约、自动读取邮箱 PIN、失败自动重试、每次运行通过邮件 + Telegram 双通道通知。

需要的东西：一只不想因忘记点击"续约"而丢失免费 VPS 的手（和账号）。

---

## 目录

1. [工作原理总览](#1-工作原理总览)
2. [前置准备与变量清单](#2-前置准备与变量清单)
3. [获取 Euserv 账号信息并开启 2FA](#3-获取-euserv-账号信息并开启-2fa)
4. [部署 Cloud Mail（推荐）并获取邮箱变量](#4-部署-cloud-mail推荐并获取邮箱变量)
5. [备选：准备 IMAP 邮箱](#5-备选准备-imap-邮箱)
6. [获取 Telegram 推送变量（可选）](#6-获取-telegram-推送变量可选)
7. [Fork 本仓库](#7-fork-本仓库)
8. [多账号续期（可选）](#75-多账号续期可选)
9. [创建 GitHub PAT](#8-创建-github-pat)
10. [把变量填入 GitHub Secrets](#9-把变量填入-github-secrets)
11. [首次手动运行并验证](#10-首次手动运行并验证)
12. [自动调度如何运作](#11-自动调度如何运作)
13. [常见问题排查](#12-常见问题排查)

---

## 1. 工作原理总览

整套系统由三部分组成：

```
GitHub Actions 定时触发
        │
        ▼
Euserv_Renewal.py (RenewalBot)
   ├─ 登录 Euserv（图片验证码/2FA 处理）
   ├─ 检查哪些服务器到了续约窗口
   ├─ 逐台续约：点续约 → 触发邮箱 PIN → 读 PIN → 换 token → 提交
   ├─ 复查结果并算出“下次续约日期”
   └─ 发送通知（邮件 + 可选 Telegram）
        │
        ▼
动态调度：用 PAT 改写 workflow 的 cron 为下次日期
```

- **谁触发**：GitHub Actions 定时（cron）或手动触发。
- **登录**：模拟浏览器请求 `support.euserv.com`。遇到图片验证码用本地 `ddddocr` 与 TrueCaptcha API **并行识别**；遇到 2FA 用你保存的 Setup key 本地生成动态码。
- **续约确认**：EUserv 会向你的邮箱发送一封主题为 `EUserv - PIN for the Confirmation of a Security Check` 的邮件，脚本从邮箱读出其中的 6 位 PIN 完成续约。
- **退出码**：`0` 成功 / `1` 失败（workflow 会 60 秒后重试，最多 3 次）/ `2` 未到期（跳过）。
- **动态调度**：每次完成后算出最早的可续约日期，用 GitHub PAT 自动改写 workflow 里的 cron，做到**只在需要续约的那天运行**。

---

## 2. 前置准备与变量清单

先把要用的**账号**和**变量**一次性列出来。后面每一节都会教你**逐个拿到**它们。

### 2.1 需要的账号

| # | 账号 | 用途 |
|---|------|------|
| 1 | **Euserv 免费 VPS 账号** | 登录 `https://support.euserv.com` 续约 |
| 2 | **Cloud Mail 部署域名**（推荐方案） | 自建邮箱服务，接收续约 PIN 邮件 |
| 3 | **163 邮箱**（或任意支持 SMTP 的邮箱） | 发送运行报告邮件（可选） |
| 4 | **Telegram 账号**（可选） | 接收运行报告推送 |
| 5 | **GitHub 账号** | Fork 仓库并运行 Actions |

### 2.2 需要收集的变量（总清单）

这些是后面要填入 GitHub Secrets 的全部变量。先混个眼熟，**获取方法见对应小节**：

| 变量名 | 是什么 | 哪里获取 |
|---|---|---|
| `EUSERV_USERNAME` | Euserv 登录邮箱 | [第 3 步](#3-获取-euserv-账号信息并开启-2fa) |
| `EUSERV_PASSWORD` | Euserv 登录密码 | [第 3 步](#3-获取-euserv-账号信息并开启-2fa) |
| `EUSERV_2FA` | Euserv 双因素认证 Setup key（推荐） | [第 3 步](#3-获取-euserv-账号信息并开启-2fa) |
| `CLOUD_MAIL_API_URL` | 你部署的 Cloud Mail 根地址，形如 `https://你部署的邮件根地址` | [第 4 步](#4-部署-cloud-mail推荐并获取邮箱变量) |
| `EMAIL_USERNAME` | Cloud Mail **管理员邮箱** | [第 4 步](#4-部署-cloud-mail推荐并获取邮箱变量) |
| `EMAIL_PASSWORD` | Cloud Mail **管理员密码** | [第 4 步](#4-部署-cloud-mail推荐并获取邮箱变量) |
| `EMAIL_HOST`（仅 IMAP 方案） | IMAP 服务器地址 | [第 5 步](#5-备选准备-imap-邮箱) |
| `SMTP_USERNAME` | 163 发信邮箱（可选） | [第 6 步](#6-获取-telegram-推送变量可选)下的小节 |
| `SMTP_PASSWORD` | 163 的 SMTP 授权码（可选） | 同上 |
| `SMTP_HOST` | SMTP 服务器地址，如 `smtp.163.com` | 同上 |
| `NOTIFICATION_EMAIL` | 收运行报告的邮箱 | 同上 |
| `TG_BOT_TOKEN` + `TG_USER_ID` | Telegram Bot 凭据（可选） | [第 6 步](#6-获取-telegram-推送变量可选) |
| `PAT_WITH_WORKFLOW_SCOPE` | GitHub 个人访问令牌 | [第 8 步](#8-创建-github-pat) |
| `CAPTCHA_USERID` + `CAPTCHA_APIKEY` | TrueCaptcha 凭据（可选） | 注册 `https://apitruecaptcha.org/` |

> **重要**：本教程中出现的「管理员邮箱」「管理员密码」「Euserv 登录邮箱」等占位文字，都要替换成你自己的真实值，任何一步都不要把真实值写进教程或仓库文件。

---

## 3. 获取 Euserv 账号信息并开启 2FA

### 3.1 Euserv 登录邮箱和密码（`EUSERV_USERNAME` / `EUSERV_PASSWORD`）

1. 打开 `https://support.euserv.com`，注册 / 登录。
2. 你能登录的那个**邮箱地址**和**密码**，就是 `EUSERV_USERNAME` 和 `EUSERV_PASSWORD` 的值。

### 3.2 开启 2FA（强烈推荐，获取 `EUSERV_2FA`）

> **为什么**：开启后 Euserv 会信任你的登录，大概率**跳过图片验证码**（省去验证码识别和 API 费用），也更安全。

1. 登录 Euserv 控制台 → 账户/安全设置 → 找到 **Two-Factor Authentication** 并开启。
2. 用任意 TOTP 应用（Google Authenticator / Authy / 微软 Authenticator）扫二维码，或手动输入密钥完成绑定。
3. 页面上出现的 **Setup key**（形如 `ABCD1234EFGH5678` 的 Base32 字符串）**保存下来**——这就是 `EUSERV_2FA` 的值。

---

## 4. 部署 Cloud Mail（推荐）并获取邮箱变量

**目标**：你的 Euserv 登录邮箱由自部署 Cloud Mail（基于 Cloudflare）托管，脚本通过其 HTTP API 读取 PIN 邮件，不依赖 IMAP 协议。

### 4.1 部署 Cloud Mail

1. 参照 [Cloud Mail 部署文档](https://github.com/maillab/cloud-mail)，把它部署到**你自己控制的一个域名**下。部署完成后你会得到一个访问地址，形如 `https://你部署的邮件根地址`（比如 `https://mail.你的域名`）。
2. 部署时/首次初始化时，Cloud Mail 会让你设置**管理员邮箱**和**管理员密码**。这两个值请保存好——它们分别是 `EMAIL_USERNAME` 和 `EMAIL_PASSWORD` 的值。
3. 打开 Cloud Mail 后台 → **用户管理**，把你的 **Euserv 登录邮箱**（即第 3 步的 `EUSERV_USERNAME`）添加为**收件用户**，确认能正常收信。这样续约 PIN 才能投递进来。

### 4.2 用 curl 验证 API 可用（拿到三个变量）

拿到管理员邮箱和密码后，先手动验证（在本地终端执行，只用一次）：

```bash
# 1) 换取 token
curl -X POST https://你部署的邮件根地址/api/public/genToken \
     -H "Content-Type: application/json" \
     -d '{"email":"管理员邮箱","password":"管理员密码"}'
# 返回 {"code":200,"data":{"token":"..."}}

# 2) 用 token 查邮件（确认能列出 EUserv 邮件）
curl -X POST https://你部署的邮件根地址/api/public/emailList \
     -H "Authorization: 上一步的token" \
     -H "Content-Type: application/json" \
     -d '{"toEmail":"Euserv登录邮箱","sendEmail":"no-reply@euserv.com","type":0,"timeSort":"desc","num":1,"size":5}'
```

如果第 2 步能看到 `EUserv - ...` 邮件，说明 Cloud Mail 接入没问题。

> **关键点**：PIN 邮件必须投递到你的 **Euserv 登录邮箱**（与 `EUSERV_USERNAME` 一致）。脚本查询 `emailList` 后会做**客户端主题过滤**（只认 `PIN for the Confirmation of a Security Check`）并选取最新一封，因此不会被"邮箱验证"等其他 PIN 邮件误伤。

到此你已拿到本节要收集的全部变量：

| 变量名 | 值来源 |
|---|---|
| `CLOUD_MAIL_API_URL` | `https://你部署的邮件根地址` |
| `EMAIL_USERNAME` | Cloud Mail **管理员邮箱** |
| `EMAIL_PASSWORD` | Cloud Mail **管理员密码** |

---

## 5. 备选：准备 IMAP 邮箱

如果你不想自建 Cloud Mail，也可以直接用任何支持 IMAP 的邮箱（例如 Gmail）：

1. 在邮箱设置中开启 IMAP（Gmail：设置 → Forwarding and POP/IMAP → 启用 IMAP）。
2. 生成**应用专用密码**（Gmail：Google 账号 → 安全 → 应用专用密码），得到 16 位形如 `abcd efgh ijkl mnop` 的密码。**不要使用登录密码**。
3. 记下 IMAP 服务地址（Gmail 为 `imap.gmail.com`）。

选择此方案时，`CLOUD_MAIL_API_URL` **不填**，`EMAIL_HOST` 必填，`EMAIL_USERNAME`/`EMAIL_PASSWORD` 换成你自己的邮箱地址 + 应用专用密码。

---

## 6. 获取 Telegram 推送变量（可选）

想让每次运行结果同时推送到 Telegram（邮件 + Telegram 双保险）：

1. 在 Telegram 找 **[@BotFather](https://t.me/BotFather)**，发送 `/newbot`，按提示创建 Bot，拿到 `TG_BOT_TOKEN`（形如 `123456:ABC-DEF...`）。
2. 给你的 Bot 私聊一句话（或把 Bot 拉进群并 @ 它）。
3. 找 **[@userinfobot](https://t.me/userinfobot)**（发送任何消息），它会回复你的 **数字 ID**，作为 `TG_USER_ID`。

### 6.1 用 163 邮箱发报告邮件（可选）

邮件告警走 **SMTP 发信**，与读取 PIN 的邮箱无关，推荐单独用一个 163 邮箱：

1. 打开 163 邮箱网页版 → 设置 → POP3/SMTP/IMAP → 开启 **SMTP 服务**，按提示用手机扫码获取**授权码**（16 位，不是登录密码）。
2. 收集以下变量：

| 变量名 | 值来源 |
|---|---|
| `SMTP_USERNAME` | 你的 163 邮箱地址 |
| `SMTP_PASSWORD` | 上一步的 163 **授权码** |
| `SMTP_HOST` | `smtp.163.com` |
| `NOTIFICATION_EMAIL` | 想收报告的收件人邮箱（可填 163 邮箱自己）|

---

## 7. Fork 本仓库

1. 打开本项目 GitHub 页面，点右上角 **Fork**，克隆到自己的账号下。
2. 之后所有配置（Secrets、手动运行）都在**你自己的仓库**进行。

---

## 7.5 多账号续期（可选）

想同时管理**多个 Euserv 账号**时，不需要新增任何变量——把每个环境变量的值用**英文逗号分隔**按位置一一对应。

**先说结论**：**账号**（`EUSERV_USERNAME/PASSWORD/2FA`）永远是逗号分隔、按位置对应；**邮箱服务**（`EMAIL_USERNAME/PASSWORD/CLOUD_MAIL_API_URL/EMAIL_HOST`）默认**共用一套**，只填一次即可，无需按账号重复。

| Secret | 单个账号 | 多个账号共用同一邮箱服务 |
|---|---|---|
| `EUSERV_USERNAME` | `user1@example.com` | `user1@example.com,user2@example.com` |
| `EUSERV_PASSWORD` | `pw1` | `pw1,pw2` |
| `EUSERV_2FA` | `KEY1` | `KEY1,KEY2` |
| `EMAIL_USERNAME` | `admin@mail.example` | `admin@mail.example`（共用，只填一次）|
| `EMAIL_PASSWORD` | `mpw` | `mpw`（共用，只填一次）|
| `CLOUD_MAIL_API_URL` | `https://mail.example` | `https://mail.example`（共用，只填一次）|
| `EMAIL_HOST`（IMAP 模式） | `imap.gmail.com` | `imap.gmail.com`（共用，只填一次）|

> 何时才需要给邮箱相关变量写多个值？**只有当多个账号各自的邮箱本来就不同**（每个账号有独立的 Cloud Mail 管理员 / 各自的 IMAP 邮箱）时才写多个值。绝大多数情况共用一套邮箱服务，只填一次。

**触发条件**：`EUSERV_USERNAME` 含逗号即进入多账号模式；不含逗号则完全按单账号运行，旧配置不受影响。

##### 示例 ①：两个账号共用同一套邮箱服务

```
EUSERV_USERNAME    = user1@example.com,user2@example.com   # 账号不同，按位置
EUSERV_PASSWORD    = pw1,pw2
EUSERV_2FA         = KEY1,KEY2
EMAIL_USERNAME     = admin@mail.example     # 邮箱服务共用，只填一次
EMAIL_PASSWORD     = mpw
CLOUD_MAIL_API_URL = https://mail.example     # 共用，只填一次
EMAIL_HOST         =                         # Cloud Mail 模式下可留空
```

##### 示例 ②：混用——账号 1 走 IMAP、账号 2 走 Cloud Mail

此例邮箱服务**不共用**：账号 1 用自己的 IMAP 邮箱收 PIN，账号 2 用 Cloud Mail API（管理员凭据不同）。关键：`EMAIL_USERNAME/PASSWORD` 必须按位置给两个账号分别填（IMAP 邮箱 ≠ Cloud 管理员），url/host 的空位要显式写出来（`url,` / `,host`）：

```
EUSERV_USERNAME    = user1@example.com,user2@example.com
EUSERV_PASSWORD    = pw1,pw2
EUSERV_2FA         = KEY1,KEY2
EMAIL_HOST         = imap.gmail.com,           # 账号1 用 IMAP；账号2 无 host（走 Cloud Mail）
CLOUD_MAIL_API_URL = ,https://mail.example   # 账号1 无 Cloud（走 IMAP）；账号2 用 Cloud Mail
EMAIL_USERNAME     = imap-mailbox@outlook.com,admin@mail.example   # 位置对应：IMAP 邮箱、Cloud 管理员
EMAIL_PASSWORD     = imap_app_pw,cloud_mpw
```

> 只填一个 `EMAIL_USERNAME`（比如只填 IMAP 邮箱）会被**广播给所有账号**，账号 2 会拿 IMAP 邮箱去 Cloud Mail 登录 → 失败。混用时必须按位置填两个不同的值。

**通知与调度**：所有账号运行结束后**汇总成一份**邮件/Telegram 报告；cron 自动设为所有账号中**最早**的下次续约日期。
**退出码**：任一账号失败则整体失败（触发 workflow 重试），全部跳过则整体跳过。

---

## 8. 创建 GitHub PAT

动态调度需要在续约后自动修改 workflow 的 cron 并 push，所以要一个带权限的 token。

1. 打开 [Fine-grained personal access tokens 页面](https://github.com/settings/personal-access-tokens/new)。
2. Token name 随意。
3. **Repository access**：选择 `Only select repositories` → 选中你 Fork 的这个仓库。
4. **Permissions**：
   - `Contents` → **Read and write**
   - `Workflows` → **Read and write**
5. 创建后**立即复制** token（只显示一次）——这就是 `PAT_WITH_WORKFLOW_SCOPE` 的值。

---

## 9. 把变量填入 GitHub Secrets

在你的 Fork 仓库：`Settings` → `Secrets and variables` → `Actions` → `New repository secret`，把第 2 步收集的变量**逐一添加**。**名称必须与变量名完全一致（含下划线、大小写），值是你在前几步收集到的真实值。**

### 必填

| Secret | 值 |
|---|---|
| `EUSERV_USERNAME` | 第 3 步的 Euserv 登录邮箱 |
| `EUSERV_PASSWORD` | 第 3 步的 Euserv 登录密码 |
| `EMAIL_USERNAME` | 第 4 步的管理员邮箱（IMAP 方案则填自己的邮箱） |
| `EMAIL_PASSWORD` | 第 4 步的管理员密码（IMAP 方案则填 App 专用密码） |

### Cloud Mail 方案额外必填

| Secret | 值 |
|---|---|
| `CLOUD_MAIL_API_URL` | `https://你部署的邮件根地址` |

### IMAP 方案额外必填

| Secret | 值 |
|---|---|
| `EMAIL_HOST` | 如 `imap.gmail.com` |

### 强烈推荐

| Secret | 值 |
|---|---|
| `EUSERV_2FA` | 第 3 步的 Setup key |
| `PAT_WITH_WORKFLOW_SCOPE` | 第 8 步的 PAT |

### 可选

| Secret | 值 | 用途 |
|---|---|---|
| `CAPTCHA_USERID` | TrueCaptcha userid | 图片验证码并行识别 |
| `CAPTCHA_APIKEY` | TrueCaptcha apikey | 同上 |
| `NOTIFICATION_EMAIL` | 收报告邮箱 | 邮件告警 |
| `SMTP_USERNAME` + `SMTP_PASSWORD` | 163 发信邮箱 + 授权码 | 邮件告警的发信凭据（独立于读取 PIN 的 `EMAIL_*`） |
| `SMTP_HOST` / `SMTP_PORT` | `smtp.163.com` / `465` | 邮件告警（Cloud Mail 模式下需手动指定） |
| `TG_BOT_TOKEN` + `TG_USER_ID` | Telegram 凭据 | Telegram 推送 |
| `TG_API_HOST` | 如 `https://api.telegram.org` | 自建代理时可改 |

> **速查**：Cloud Mail 模式下 `EMAIL_HOST` 可留空，`CLOUD_MAIL_API_URL` 必填；IMAP 模式下 `CLOUD_MAIL_API_URL` 留空，`EMAIL_HOST` 必填。二者不可同时少填。
>
> **发信提醒**：邮件告警走的是 **SMTP 发信**，与读取 PIN 的邮箱**无关**。Cloud Mail 模式下请单独配置 `SMTP_USERNAME`/`SMTP_PASSWORD`（如 163 邮箱 + 授权码）+ `SMTP_HOST`，否则运行结束不会收到报告邮件。

---

## 10. 首次手动运行并验证

1. 仓库首页点击 **`Actions`** 标签。
2. 左侧选择 **`Euserv VPS Renewal`** 工作流。
3. 右上角 **`Run workflow`** → 选择手动触发。
4. 点进运行中的 job，观察实时日志：
   - `登录成功`
   - `发现 N 台服务器合同`
   - 若已到期续约，出现 `成功获取续期Token`（说明 PIN 已被读到）
   - 结束输出 `📅 下次续约日期`
5. 查看 `NOTIFICATION_EMAIL` 或 Telegram：应收到一条 `Euserv 自动续约运行报告` 的通知。

若一切正常，之后 cron（动态调度）会在下次续约窗口运行，无需再手动触发。

---

## 11. 自动调度如何运作

- 默认 workflow `renewal.yml` 带初始 cron（如 `0 0 22 8 *`）用于首次测试。
- 每次运行后，脚本计算最早续约日期，写入 `GITHUB_OUTPUT` 的 `next_cron`。
- 后续 step 用 `PAT_WITH_WORKFLOW_SCOPE` 改写 `renewal.yml` 的 cron 并 push，实现**下次只在那天运行**。
- 失败时：workflow 外层 shell 会每 60 秒重试，最多 3 次；全部失败则本次标记失败，下一 cron 仍挂着，可人工再触发。

---

## 12. 常见问题排查

| 现象 | 处理 |
|---|---|
| 日志报 `必要的配置未设置` | 按第 9 步核对 Secret 名称与值（大小写/下划线） |
| `卡在验证码` | 检查 `CAPTCHA_USERID/KEY`，或开 2FA 跳过；验证码失败会保存 `captcha_failed.png`（可上传 artifact 排查） |
| `无法获取PIN` | 先看是否已配置邮箱 Secrets；Cloud Mail 模式下确认 `EMAIL_USERNAME`/`EMAIL_PASSWORD` 是**管理员账号**且能 genToken；IMAP 模式核对主机与 App 密码 |
| 邮件/Telegram 不推送 | 邮件：Cloud Mail 模式下需单独配置 `SMTP_USERNAME`/`SMTP_PASSWORD` + `SMTP_HOST`（163 发信邮箱+授权码）；TG：确认 TOKEN 有效、用户已私聊推送过 Bot |
| 一直 `跳过` | 未到续约窗口是正常的，动态调度会把下次日期安排到到期日 |
| 页面结构变了 | 项目以固定 DOM 结构解析，EUserv 改版后需要更新 `_parse_server_row` 的选择器 |

---

## 结语

到此，你的 EUserv 免费 VPS 已经进入**无人值守自动化续约**状态。之后要做的只有：偶尔看看推送的日志，以及每年认真做好一次配置迁移（EUserv 偶尔改版）。

> 项目按 GPL-3.0 开源，"原样"提供。EUserv 随时可能改变站点结构导致脚本失效，请自担使用风险。
