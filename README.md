# EUserv 免费 VPS 自动续约脚本 (Requests 版)

[![许可证: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0) [![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=Michaol_euserv-renewal-bot&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=Michaol_euserv-renewal-bot) ![Badge](https://hitscounter.dev/api/hit?url=https%3A%2F%2Fgithub.com%2FMichaol%2Feuserv-renewal-bot&label=&icon=github&color=%23198754&message=&style=flat&tz=Asia%2FShanghai)

一个基于 GitHub Actions 和 `requests` 库的自动化脚本，用于自动续约 [EUserv](https://www.euserv.com/) 提供的免费 VPS 计划。脚本通过精确模拟浏览器请求和邮件交互，实现无人值守的自动化续约。

---

## 目录

- [中文版](#中文版)
  - [更新记录](#更新记录)
  - [功能特性](#功能特性)
  - [配置指南](#配置指南)
  - [定时任务配置](#定时任务配置)
  - [许可证](#许可证)
  - [免责声明](#免责声明)
- [English Version](#english-version)
  - [Changelog](#changelog)
  - [Features](#features)
  - [Setup Guide](#setup-guide)
  - [Schedule Configuration](#schedule-configuration)
  - [License](#license)
  - [Disclaimer](#disclaimer)

---

## 中文版

### 更新记录

#### v2.6.0 (2026-08-07) - 中文

##### 🆕 新功能

- 👥 **多账号续期**：无需新增变量，把同一环境变量（`EUSERV_USERNAME`、`EUSERV_PASSWORD`、`EUSERV_2FA`、`EMAIL_USERNAME`、`EMAIL_PASSWORD`、`CLOUD_MAIL_API_URL`、`EMAIL_HOST`）的值用英文逗号分隔，按位置一一对应即可批量续约多个 Euserv 账号。所有账号日志汇总为一份邮件/Telegram 报告；cron 自动取最早的续约窗口；任一账号失败则整体失败并触发重试。

#### v2.5.0 (2026-08-07) - 中文

##### 🆕 新功能

- 🤖 **Telegram 推送**：新增 `TG_BOT_TOKEN` / `TG_USER_ID`（可选 `TG_API_HOST`）配置，运行结束或配置出错时自动把完整日志以 HTML 推送到 Telegram，与邮件报告并行。
- 📧 **独立 SMTP 发信凭据**：新增 `SMTP_USERNAME` / `SMTP_PASSWORD`（163 等发信邮箱 + 授权码），Cloud Mail 模式下邮件报告不再与管理员账号绑定，可正常推送。

#### v2.4.0 (2026-08-07) - 中文

##### 🆕 新功能

- ☁️ **Cloud Mail API 邮箱支持**：新增 `CLOUD_MAIL_API_URL` 配置，可通过自托管 Cloud Mail 的 HTTP API（`genToken` + `emailList`）读取续约 PIN，无需 IMAP 协议；未配置时自动回退 IMAP。
- 🗂️ **续约 PIN 精确过滤**：客户端按主题 `PIN for the Confirmation of a Security Check` 匹配并取 `createTime` 最新一封，避免误取 "Email Validation" 等其他 PIN 邮件。
- 🏁 **验证码并行识别**：本地 `ddddocr` 与 TrueCaptcha API **并行竞速**（原为顺序兜底），任一成功即用，识别成功率显著提升。

##### 配置变更

- `EMAIL_HOST` 变为可选（配置 Cloud Mail 时不再强制要求）
- `EMAIL_USERNAME` / `EMAIL_PASSWORD` 在 Cloud Mail 模式下对应**管理员邮箱**及密码

#### v2.3.1 (2026-04-16) - 中文

##### 关键修复

- 🔴 **修复验证码丢失**：修复首次登录触发验证码时 `sess_id` 未及时同步引起的验证码提交失败
- 🔴 **增强邮件重试网络恢复**：IMAP 连接断开或认证异常将触发条件重试，遇到网络波动不再直接崩毁
- 🔴 **修复状态邮件误报**：使用智能调度跳过续约时（未到期），邮件报告明确标记为“跳过”而非误报“成功”
- 🟡 **修复续期状态覆写**：增加 `_safe_refresh_session()`，避免续期成功后附带的刷新 session 失败覆写主干成功状态

##### 优化改进

- 🛡️ **统一请求源头**：统一所有请求 `Origin` 头为 `https://support.euserv.com`，防范风控拦截
- 🔧 **构建完善**：添加 `pyproject.toml` 规范环境与 pytest pythonpath (移除 `sys.path` hack)，清理无效冗余返回值和注释

#### v2.3.0 (2026-04-05) - 中文

##### 稳定性修复

- 🔴 **Session 过期自动重连**：新增 `_refresh_session()` 方法，续期流程耗时较长后自动重新登录，防止 `_check_post_renewal_status` 因 session 过期而失败
- 📧 **邮件编码兼容**：`_extract_email_body()` 使用 `part.get_content_charset()` 获取真实编码，支持多种邮件编码格式，避免 UTF-8 硬编码导致的解码失败

##### 代码质量

- 🔧 简化 `_handle_captcha` 参数（7→3），直接从实例读取凭据
- 🔧 简化 `_handle_2fa` 参数（3→1），内联 origin header 保持原始 `https://www.euserv.com`
- 🔧 `_renew` 返回值从 `bool` 改为 `None`（始终返回 True 无意义）
- 🔧 提取 `SERVER_LIST_RETRY_DELAY` 常量，替代 `sleep(30)` 硬编码
- 🗑️ 移除多余的 `http://` 重试适配器（Euserv 纯 HTTPS）

##### 测试改进

- ✅ 修正测试名 `test_parentheses_not_supported` → `test_parentheses_work`
- 🧹 移除 `test_safe_eval.py` 中未使用的 `pytest` import

##### CI 优化

- ⚡ 启用 Node.js 24，消除 GitHub Actions 弃用警告

<details>
<summary>v2.2.0 及更早版本</summary>

#### v2.2.0 (2026-02-19)

##### 关键修复

- 🔴 **修复 cron 调度不更新**：空服务器列表不再静默成功，改为 `EXIT_FAILURE` 并保存调试页面
- 🔴 **修复续约后 cron 丢失**：无论续约状态如何均输出下次续约日期
- 🔴 **修复测试套件**：修复因函数重命名导致的 ImportError（3 个测试文件）

##### 安全加固

- 🔒 2FA 密码和 PIN 码日志遮蔽，仅显示末 2 位
- 🛡️ 新增 `HTTPAdapter` + `Retry` 自动重试策略（5xx 状态码）
- 🌐 User-Agent 更新至 Chrome 131

##### 优化改进

- 🎯 使用 `ddddocr.set_ranges()` 限制字符集，提高数学验证码识别率
- 🧹 提取 `_clean_math_expr()` / `_try_solve_math()` 统一数学表达式处理
- 🧹 提取 `_parse_server_row()` 降低认知复杂度
- 📊 服务器列表解析增加行数日志，空结果保存 HTML 用于调试

#### v2.1.0 (2026-01-22)

##### 架构优化

- 🏗️ **Phase 3 架构统一**：将 15+ 顶层函数移入 `RenewalBot` 类
- 🧹 消除全局变量 `LOG_MESSAGES`, `CURRENT_LOGIN_ATTEMPT`, `_ocr_instance`
- ⚡ OCR 预热：启动时预加载模型，减少首次识别延迟
- 🔒 HTTP Session 资源管理：添加 `_cleanup()` 方法确保正确关闭

##### 测试覆盖

- 🧪 新增 pytest 测试套件 (`tests/test_renewal.py`)
- 🎯 9 个测试类覆盖核心功能

##### 代码质量

- 📝 10+ 函数添加完整类型注解
- 🎯 10 个常量提取 (字符串 + URL)
- 🔧 降低认知复杂度，拆分复杂方法

#### v2.0.0 (2026-01-15)

##### 安全性与稳定性

- 🔒 移除不安全的 `eval()`，替换为基于 AST 的安全表达式解析器
- ⏱️ 为所有 HTTP 请求添加 30 秒超时，防止脚本挂起
- 📦 锁定依赖版本，确保构建一致性

##### 代码质量 (v2.0.0)

- 🏗️ 新增 `RenewalBot` 类封装全局状态，提高可测试性
- 🧪 添加 21 个单元测试覆盖核心功能
- 📝 添加类型注解和 `LogLevel` 枚举统一日志格式
- ⚡ OCR 实例缓存，避免重复加载模型

##### 配置增强

- 📧 支持自定义 `SMTP_HOST` 和 `SMTP_PORT` 环境变量
- ✅ 新增启动时配置验证，明确提示缺失项

</details>

### 功能特性

- 通过 GitHub Actions 自动续约 Euserv 免费 VPS。
- 处理登录、会话及**两步验证(2FA)**。
- **三保险验证码识别**：本地 OCR (`ddddocr`) 与 TrueCaptcha API **并行竞速**，任一成功即用。
- 获取续约 PIN 码：支持 **Cloud Mail API**（自建邮箱，推荐）或 **IMAP**（Gmail 等）两种方式。
- 完整实现包含 Token 验证的精确续约流程。
- 每次运行后通过邮件发送状态报告。
- 所有凭据均通过 GitHub Secrets 安全管理。

### 配置指南

要使此项目正常工作，请严格遵循以下步骤。

> 💡 想要**一步一步跟着做完**的完整新手教程？请阅读 [DEPLOY.md — 从零开始的详细部署教程](./DEPLOY.md)。下面这份是各步骤的浓缩速查版。

#### 准备工作

按顺序准备以下四项：

1. **Euserv 免费 VPS 账户**，且能正常登录后台（`https://support.euserv.com`）。
2. 一个**用于接收续约 PIN 的邮箱**，满足以下**任选其一**：
   - **Cloud Mail（推荐）**：自部署的 [Cloud Mail](https://github.com/maillab/cloud-mail)（基于 Cloudflare），通过 HTTP API 读取邮件，无 IMAP 协议要求，适合域名邮箱；
   - **或** 任意支持 IMAP 的邮箱（如 Gmail），并为它生成一个**应用专用密码（App Password）**（不是你的登录密码）。
3. **（可选）一个 TrueCaptcha 账户**（注册地址 `https://apitruecaptcha.org/`），作为本地 OCR 之外的并行识别通道；只在图片验证码时常出现时才有必要。
4. **一个 GitHub 账户**，用于托管你 Fork 后的仓库并运行 Actions。

> 三点快速说明：
> - **登录验证码与续约 PIN 是两回事**。登录可能遇到的是图片验证码（数学算式）或 2FA 动态码（由 `EUSERV_2FA` Setup key 在本地 TOTP 生成）；续约确认时才收到邮箱 PIN 邮件（主题 `EUserv - PIN for the Confirmation of a Security Check`），由邮箱模块（Cloud Mail API 或 IMAP）读取。两者互不影响。
> - `EUSERV_2FA` 开启后，Euserv 通常信任你的登录并**跳过图片验证码**，`CAPTCHA_*` 基本用不到；未开 2FA 时才真正依赖 `ddddocr` + `CAPTCHA_*` 并行通道。

#### 第 1 步：Fork 本仓库

- 点击本页面右上角的 **`Fork`** 按钮，把项目复制到你自己的 GitHub 账户下。
- Fork 完成后，你之后所有配置都应在你**自己的仓库**中进行，而不是原始仓库。

> **安全建议**：任何时刻都不要把个人凭据写进代码或 push 到仓库，所有敏感信息一律通过 GitHub Secrets 注入。

#### 第 2 步（强烈推荐）：在 Euserv 后台开启 2FA

> 此步**强烈推荐**：开启 2FA 后，Euserv 会信任你的登录行为，很可能**跳过图片验证码**，能省去验证码识别成本，也能避免账号被盗。

1. 登录 Euserv 控制台 → 进入账户/安全设置，找到 **Two-Factor Authentication** 选项并开启。
2. 按页面向导，用任意 TOTP 应用（Google Authenticator / Authy / 微软 Authenticator 等）扫码，或者手动输入密钥。
3. 页面会给出一个 **Setup key**（形如 `ABCD1234EFGH5678` 的 Base32 字符串）——**把它保存下来**，等下填入 `EUSERV_2FA` secret。
4. 完成绑定，并验证动态码可用。

#### 第 3 步：准备邮箱（二选一）

**方案 A：Cloud Mail（推荐，免 IMAP）**

1. 参照 [Cloud Mail 部署文档](https://github.com/maillab/cloud-mail) 把 Cloud Mail 部署到你自己的域名上（部署完成后会得到一个根地址，形如 `https://你部署的邮件根地址`）。
2. 打开 Cloud Mail 后台 → **用户管理**，把你的 **Euserv 登录邮箱**添加为**收件用户**（确认可以正常收信）。
3. 记住你的 Cloud Mail **管理员账号邮箱**和密码——它用于 `genToken` 换取令牌。你可以用 curl 预验证：
   ```bash
   curl -X POST https://你部署的邮件根地址/api/public/genToken \
        -H "Content-Type: application/json" \
        -d '{"email":"管理员邮箱","password":"管理员密码"}'
   # 应返回 {"code":200,"data":{"token":"..."}}
   ```
4. 再用返回的 token 试查邮件列表：
   ```bash
   curl -X POST https://你部署的邮件根地址/api/public/emailList \
        -H "Authorization: <上一步的token>" \
        -H "Content-Type: application/json" \
        -d '{"toEmail":"你的Euserv登录邮箱","sendEmail":"no-reply@euserv.com","type":0,"timeSort":"desc","num":1,"size":5}'
   ```
   能看到 `EUserv - PIN for ...` 邮件即表示可用。

**方案 B：IMAP 邮箱（如 Gmail）**

1. 在邮箱提供商处开启 IMAP 协议（Gmail：设置 → Forwarding and POP/IMAP → 启用 IMAP）。
2. 为你的邮箱生成**应用专用密码**（Gmail：Google 账号 → 安全 → 应用专用密码，生成一个 16 位密码，形如 `abcd efgh ijkl mnop`）。不要使用你在 Gmail 登录时使用的密码。
3. 记下 IMAP 服务器地址（Gmail 为 `imap.gmail.com`）。

#### 第 4 步：创建 GitHub PAT（动态调度用）

动态调度说明：续约完成后自动把 cron 改成下次续约日期，需要脚本有权限 push 工作流文件。

1. 打开 [Fine-grained personal access tokens](https://github.com/settings/personal-access-tokens/new) 创建：
   - Token name 随意；
   - **Repository access**：选 `Only select repositories` → 选中你 Fork 的这个仓库；
   - **Permissions**：把 `Contents` 设为 **Read and write**，`Workflows` 设为 **Read and write**。
2. 创建后**立即**复制 token（只显示一次），粘贴为下面 `PAT_WITH_WORKFLOW_SCOPE` 的值。
3. （找不到该 token ？）可在仓库设置里事后重新生成一个替换。

#### 第 5 步：配置 GitHub Secrets

这是**最关键的步骤**。请在 Fork 后的仓库内：`Settings` 标签页 → `Secrets and variables` → `Actions` → 点击 **`New repository secret`** 逐一添加。**Secret 名称必须与下面表格完全一致**（区分大小写）。

| Secret               | 示例值                          | 说明                                                                                                                                                              |
|----------------------|--------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `EUSERV_USERNAME`    | `your_euserv_username`          | Euserv 登录账号（用户名或邮箱）。                                                                                                                                |
| `EUSERV_PASSWORD`    | `your_euserv_password`          | Euserv 登录密码。                                                                                                                                               |
| `EUSERV_2FA`         | `ABCD1234EFGH5678`              | **(可选，强烈建议)** 第 2 步保存的 **Setup key**，用于本地生成 TOTP 动态码。开 2FA 后可跳过图片验证码。                                                            |
| `CAPTCHA_USERID`     | `your_captcha_userid`           | **(可选)** TrueCaptcha 的 `userid`，与本地 OCR 并行识别图片验证码。                                                                                                |
| `CAPTCHA_APIKEY`     | `xxxxxxxxxxxxxxxxxxxx`          | **(可选)** TrueCaptcha 的 `apikey`，同上。                                                                                                                        |
| `EMAIL_HOST`         | `imap.gmail.com`                | 邮箱 IMAP 服务器地址。**Cloud Mail 模式时可留空不填**；IMAP 模式下必填。                                                                                           |
| `EMAIL_USERNAME`     | `your_email@gmail.com`           | **IMAP 模式**：完整邮箱地址；**Cloud Mail 模式**：管理员**账号邮箱**。                                                                                           |
| `EMAIL_PASSWORD`     | `abcd efgh ijkl mnop`            | **IMAP 模式**：应用专用密码**；**Cloud Mail 模式**：管理员邮箱密码。                                                                                            |
| `CLOUD_MAIL_API_URL` | `https://你部署的邮件根地址` | **(可选)** 自置 Cloud Mail 的 API 根地址。设置了就走 Cloud Mail API（推荐）；未设置则回退 IMAP 模式。                                                               |
| `NOTIFICATION_EMAIL` | `your_notify_email@example.com` | 接收运行报告的邮箱。不填则不发报告邮件，但脚本仍正常执行。                                                                                                     |
| `SMTP_USERNAME`      | `user@163.com`                  | **(可选)** SMTP 登录账号（发信邮箱，如 163/Gmail 及其应用专用密码）。**默认回退用 `EMAIL_USERNAME`**；Cloud Mail 模式下必须单独指定，否则无法发信。                 |
| `SMTP_PASSWORD`      | `smtp_auth_code`                | **(可选)** 与 `SMTP_USERNAME` 对应的 SMTP 密码（163 用「授权码」）。同上方回退规则。                                                                                 |
| `SMTP_HOST`          | `smtp.gmail.com`                 | **(可选)** SMTP 服务器地址。不填则依据 `EMAIL_HOST`（把 `imap` 替换为 `smtp`）推断；Cloud Mail 模式下需要手动指定，否则无法发报告。                                  |
| `SMTP_PORT`          | `587`                             | **(可选)** SMTP 端口。默认 587。                                                                                                                            |
| `TG_BOT_TOKEN`       | `123456:ABC-DEF...`               | **(可选)** Telegram Bot Token。配置后运行报告会同时推送到 Telegram。详见下方「Telegram 推送」。                                                         |
| `TG_USER_ID`         | `123456789`                        | **(可选)** 接收 Telegram 消息的用户/群组 ID。                                                                                                              |
| `TG_API_HOST`        | `https://api.telegram.org`        | **(可选)** Telegram API 地址（默认官方，自建代理时修改）。                                                                                                  |
| `PAT_WITH_WORKFLOW_SCOPE` | `github_pat_xxx`                | **(推荐)** 第 4 步创建的 [Fine-grained PAT](https://github.com/settings/personal-access-tokens/new)，用于动态调度更新 cron。权限：`Contents` (RW) 和 `Workflows` (RW)。 |

**两种邮箱方案的 Secret 配置速查**

| Secret | Cloud Mail 模式（推荐） | IMAP 模式 |
|---|---|---|
| `EMAIL_HOST` | 不填 | `imap.gmail.com` |
| `EMAIL_USERNAME` | Cloud Mail 管理员邮箱 | 你的完整邮箱地址 |
| `EMAIL_PASSWORD` | 管理员邮箱密码 | 应用专用密码 |
| `CLOUD_MAIL_API_URL` | 必填，如 `https://你部署的邮件根地址` | 不填 |

#### Telegram 推送（可选）

若希望续约结果同时推送到 Telegram（替代或配合邮件告警）：

1. 找 [@BotFather](https://t.me/BotFather) 创建 Bot，拿到 `TG_BOT_TOKEN`（形如 `123456:ABC-DEF...`）。
2. 与你的 Bot 私聊一句（或在群里 @ 它），然后向 [@userinfobot](https://t.me/userinfobot) 查你自己的 `TG_USER_ID`（数字）。
3. 配置 Secrets：`TG_BOT_TOKEN`、`TG_USER_ID`（**可选**：`TG_API_HOST`，用于自建代理）。
4. 运行结束或配置出错时，`send_telegram_notification()` 会把本次完整日志以 HTML 格式推送到你的 Telegram。

> 长日志默认截断至 4000 字符左右，显示"（日志过长已截断）"。

#### 多账号续期（可选）

想同时管理**多个 Euserv 账号**时，**不需要新增任何变量**——把每个环境变量的值用**英文逗号分隔**，按位置一一对应即可。

**先说结论**：
- **账号是不同的**（登录名、密码、2FA）→ 永远逗号分隔，按位置一一对应。
- **邮箱服务是共用的**（同一个 Cloud Mail 实例 / 同一套 IMAP）→ 只填一个值就行，其余账号自动继承。
- **邮箱服务要分开**（账号 1 走 IMAP、账号 2 走 Cloud Mail）→ 见下面专门示例，需写空位。

| Secret | 单个账号 | 多个账号共用同一邮箱服务 |
|---|---|---|
| `EUSERV_USERNAME` | `user1@example.com` | `user1@example.com,user2@example.com` |
| `EUSERV_PASSWORD` | `pw1` | `pw1,pw2` |
| `EUSERV_2FA` | `KEY1` | `KEY1,KEY2` |
| `EMAIL_USERNAME` | `admin@mail.example` | `admin@mail.example`（共用，只填一次）|
| `EMAIL_PASSWORD` | `mpw` | `mpw`（共用，只填一次）|
| `CLOUD_MAIL_API_URL` | `https://mail.example` | `https://mail.example`（共用，只填一次）|
| `EMAIL_HOST`（IMAP 模式） | `imap.gmail.com` | `imap.gmail.com`（共用，只填一次）|

> 什么时候需要给 `EMAIL_USERNAME/PASSWORD/CLOUD_MAIL_API_URL/EMAIL_HOST` 也写多个值？
> **只有当多个账号各自的邮箱本来就不同**（每个账号有自己独立的 Cloud Mail 管理员 / 各自的 IMAP 邮箱）时才写多个值。绝大多数情况它们共用一套，只填一次。

**触发条件**：`EUSERV_USERNAME` 含逗号即进入多账号模式；不含逗号则完全按单账号运行，旧配置不受影响。

**通知与调度**：所有账号运行结束后**汇总成一份**邮件/Telegram 报告；cron 自动设为所有账号中**最早**的下次续约日期；任一账号失败则整体失败（触发重试）。

##### 多账号示例 ①：两个账号共用同一套邮箱服务

账号 1 和账号 2 的 Euserv 账号不同，但都用**同一个** Cloud Mail 实例（或同一套 IMAP）收 PIN：

```
EUSERV_USERNAME    = user1@example.com,user2@example.com   # 按位置
EUSERV_PASSWORD    = pw1,pw2
EUSERV_2FA         = KEY1,KEY2
EMAIL_USERNAME     = admin@mail.example     # 共用，只填一次
EMAIL_PASSWORD     = mpw
CLOUD_MAIL_API_URL = https://mail.example     # 共用，只填一次
EMAIL_HOST         =                         # Cloud Mail 模式下可留空
```

##### 多账号混用 ②：账号 1 走 IMAP、账号 2 走 Cloud Mail

此时**邮箱服务要分开**——账号 1 用自己的 IMAP 邮箱收 PIN，账号 2 用 Cloud Mail API 收 PIN（管理员凭据不同）。关键：`EMAIL_USERNAME/PASSWORD` 必须按位置给两个账号分别填（IMAP 邮箱 ≠ Cloud 管理员），并把 url/host 空位显式写出来：

```
EUSERV_USERNAME    = user1@example.com,user2@example.com
EUSERV_PASSWORD    = pw1,pw2
EUSERV_2FA         = KEY1,KEY2
EMAIL_HOST         = imap.gmail.com,           # 账号1 用 IMAP；账号2 无 host（走 Cloud）
CLOUD_MAIL_API_URL = ,https://mail.example   # 账号1 无 Cloud（走 IMAP）；账号2 用 Cloud
EMAIL_USERNAME     = imap-mailbox@outlook.com,admin@mail.example   # 位置对应：IMAP 邮箱、Cloud 管理员
EMAIL_PASSWORD     = imap_app_pw,cloud_mpw
```

> 只填一个 `EMAIL_USERNAME`（比如只填 IMAP 的邮箱）时，它会被**广播给所有账号**，账号 2 就会拿 IMAP 邮箱去 Cloud 登录 → 失败。所以混用时必须按位置填两个不同的值。

#### 第 6 步：手动运行工作流测试

1. 在仓库首页点 **`Actions`** 标签。
2. 左侧选择 **`Euserv VPS Renewal`** 工作流。
3. 点右侧 **`Run workflow`** → 确认后手动触发一次。
4. 点进运行中的 job，查看实时日志，重点观察：
   - `登录成功`（或出现验证码/2FA 的处理日志）；
   - `发现 N 台服务器合同`；
   - 检测到需要续约时，`成功获取续期Token`、PIN 是否被读取（日志只会显示末尾 2 位）；
   - 最后输出 📅 下次续约日期。

> 默认脚本在请求 PIN 后等待 **30 秒** 再读取邮箱。如果邮件接收有延迟，把 `Euserv_Renewal.py` 顶部的 `WAITING_TIME_OF_PIN` 改成 `60`。同理 Cloud Mail 模式下可用 `EMAIL_CHECK_INTERVAL` 控制轮询间隔。

#### 常见问题排查

| 现象 | 思路 |
|---|---|
| 日志报 `必要的配置未设置` | 按第 5 步纠正 Secret 名称（大小写、下划线必须一致）。 |
| `登录失败次数过多` | 检查 `EUSERV_USERNAME/PASSWORD`；如看到验证码多次失败，检查 `CAPTCHA_*` 或开启 2FA 跳过验证码。 |
| `无法获取 PIN` | Cloud Mail 模式下确认 `EMAIL_USERNAME/PASSWORD` 是**管理员账号**且能 genToken；IMAP 模式下确认应用专用密码及 `EMAIL_HOST` 正确。 |
| 邮件报告迟迟不发 | Cloud Mail 模式下需要单独填 `SMTP_USERNAME`/`SMTP_PASSWORD`（发信邮箱+授权码）+ `SMTP_HOST`，因为 `EMAIL_*` 是管理员账号、不是 SMTP 凭据，且 `SMTP_HOST` 不会从 IMAP 推断。 |
| 每次运行都收到 "跳过" | 正常，表示未到续约窗口，动态调度会安排下次。 |

### 定时任务配置

脚本采用**动态调度机制**：

| 特性     | 说明                                                               |
| -------- | ------------------------------------------------------------------ |
| 动态调度 | 续约完成后自动更新 cron 为下次续约日期，只在需要时运行，零额外消耗 |
| 失败重试 | 失败后每 30 分钟重试，最多 3 次                                    |
| 跨天续试 | 当天全部失败后，第二天自动继续尝试                                 |
| PAT 要求 | 需要配置 `PAT_WITH_WORKFLOW_SCOPE` Secret 以启用动态调度           |

创建 PAT：[创建 Fine-grained Token](https://github.com/settings/personal-access-tokens/new)

1. **Repository access**: 选择 `Only select repositories` -> 选择本仓库
2. **Permissions**: 展开并设置 `Contents` 为 **Read and write**，`Workflows` 为 **Read and write**

### 许可证

该项目根据 **GNU General Public License v3.0** 许可证授权。详情请参阅 `LICENSE` 文件。

### 免责声明

- 本项目按"原样"提供，作者不对任何因使用此脚本可能导致的服务中断、数据丢失或其他损失负责。
- EUserv 随时可能更改其网站结构或续约流程，这可能导致此自动化脚本失效。
- 请自行承担使用风险。

---

## English Version

### Changelog

#### v2.6.0 (2026-08-07) - English

##### 🆕 New Features

- 👥 **Multi-account renewal**: no new variables needed — put comma-separated values in the same env vars (`EUSERV_USERNAME`, `EUSERV_PASSWORD`, `EUSERV_2FA`, `EMAIL_USERNAME`, `EMAIL_PASSWORD`, `CLOUD_MAIL_API_URL`, `EMAIL_HOST`), aligned by position, to renew several Euserv accounts in one run. All account logs are aggregated into a single email/Telegram report; the cron is set to the earliest renewal window; if any account fails, the whole run fails and triggers the retry.

#### v2.5.0 (2026-08-07) - English

##### 🆕 New Features

- 🤖 **Telegram notifications**: new `TG_BOT_TOKEN` / `TG_USER_ID` (optional `TG_API_HOST`) secrets push the full run log to Telegram as HTML in parallel with the email report.
- 📧 **Separate SMTP sender credentials**: new `SMTP_USERNAME` / `SMTP_PASSWORD` (e.g., a 163 mailbox + app/auth code) let the email report push work in Cloud Mail mode, decoupled from the admin account.

#### v2.4.0 (2026-08-07) - English

##### 🆕 New Features

- ☁️ **Cloud Mail API mailbox support**: new `CLOUD_MAIL_API_URL` option reads the renewal PIN via self-hosted Cloud Mail's HTTP API (`genToken` + `emailList`), removing the IMAP requirement; automatically falls back to IMAP when unset.
- 🗂️ **Precise renewal-PIN selection**: client-side exact match on the subject `PIN for the Confirmation of a Security Check` and picks the newest by `createTime`, avoiding false hits from "Email Validation" and other PIN mails.
- 🏁 **Parallel CAPTCHA solving**: local `ddddocr` and TrueCaptcha API now race concurrently (previously sequential fallback); whichever succeeds first is used, significantly boosting recognition.

##### Config Changes

- `EMAIL_HOST` is now optional when Cloud Mail is configured
- `EMAIL_USERNAME` / `EMAIL_PASSWORD` map to the **admin mailbox** account in Cloud Mail mode

#### v2.3.1 (2026-04-16) - English

##### Critical Fixes

- 🔴 **Fix CAPTCHA failure**: Fixed an issue where `sess_id` was not synchronized during the first login attempt, causing CAPTCHA submission to fail
- 🔴 **Enhance email retry capability**: IMAP connection drops or auth exceptions now trigger conditional retries instead of crashing immediately on temporary network issues
- 🔴 **Fix status email misinformation**: When smart scheduling skips renewal (not due yet), the email report is explicitly marked as "Skipped" instead of falsely reporting "Success"
- 🟡 **Fix renewal status override**: Added `_safe_refresh_session()` to prevent a session refresh failure from overwriting a successful renewal status

##### Improvements

- 🛡️ **Unified request origin**: Unified all `Origin` headers to `https://support.euserv.com` to prevent potential WAF blocks
- 🔧 **Build system**: Added `pyproject.toml` for standardizing environments and pytest `pythonpath` (removed `sys.path` hacks), cleaned up redundant return values

#### v2.3.0 (2026-04-05) - English

##### Stability Fixes

- 🔴 **Session expiry auto-recovery**: Added `_refresh_session()` method to re-login after long renewal flows, preventing `_check_post_renewal_status` failures due to expired sessions
- 📧 **Email encoding compatibility**: `_extract_email_body()` now uses `part.get_content_charset()` with UTF-8 fallback, supporting multiple email encodings

##### Code Quality

- 🔧 Simplified `_handle_captcha` parameters (7→3), reads credentials from instance directly
- 🔧 Simplified `_handle_2fa` parameters (3→1), inlines origin header to preserve original `https://www.euserv.com`
- 🔧 Changed `_renew` return type from `bool` to `None` (was always returning True)
- 🔧 Extracted `SERVER_LIST_RETRY_DELAY` constant, replacing hardcoded `sleep(30)`
- 🗑️ Removed redundant `http://` retry adapter (Euserv is exclusively HTTPS)

##### Test Improvements

- ✅ Fixed test name `test_parentheses_not_supported` → `test_parentheses_work`
- 🧹 Removed unused `pytest` import from `test_safe_eval.py`

##### CI Optimization

- ⚡ Enabled Node.js 24 to silence GitHub Actions deprecation warning

<details>
<summary>v2.2.0 and earlier</summary>

#### v2.2.0 (2026-02-19)

##### Critical Fixes

- 🔴 **Fix cron schedule not updating**: Empty server list now returns `EXIT_FAILURE` and saves debug HTML
- 🔴 **Fix next_cron lost after renewal**: Always output next renewal date regardless of post-renewal status
- 🔴 **Fix test suite**: Resolved ImportError in 3 test files caused by function renaming

##### Security Hardening

- 🔒 Mask 2FA codes and PINs in logs (show only last 2 digits)
- 🛡️ Added `HTTPAdapter` + `Retry` strategy for automatic retries on 5xx errors
- 🌐 Updated User-Agent to Chrome 131

##### Improvements

- 🎯 Use `ddddocr.set_ranges()` to constrain character set for better math CAPTCHA accuracy
- 🧹 Extracted `_clean_math_expr()` / `_try_solve_math()` for unified math expression handling
- 🧹 Extracted `_parse_server_row()` to reduce cognitive complexity
- 📊 Added row count logging for server list parsing; save HTML on empty results for debugging

#### v2.1.0 (2026-01-22)

##### Architecture Optimization

- 🏗️ **Phase 3 Architecture Unification**: Moved 15+ top-level functions into `RenewalBot` class
- 🧹 Eliminated global variables `LOG_MESSAGES`, `CURRENT_LOGIN_ATTEMPT`, `_ocr_instance`
- ⚡ OCR Prewarming: Preload model at startup to reduce first recognition delay
- 🔒 HTTP Session Resource Management: Added `_cleanup()` method for proper closure

##### Test Coverage

- 🧪 Added pytest test suite (`tests/test_renewal.py`)
- 🎯 9 test classes covering core functionality

##### Code Quality

- 📝 10+ functions with complete type annotations
- 🎯 10 constants extracted (strings + URLs)
- 🔧 Reduced cognitive complexity by splitting complex methods

#### v2.0.0 (2026-01-15)

##### Security and Stability

- 🔒 Replaced unsafe `eval()` with AST-based safe expression parser
- ⏱️ Added 30-second timeout to all HTTP requests
- 📦 Locked dependency versions for consistent builds

##### Code Quality (v2.0.0)

- 🏗️ Added `RenewalBot` class to encapsulate global state
- 🧪 Added 21 unit tests covering core functionality
- 📝 Added type annotations and `LogLevel` enum for unified logging
- ⚡ Cached OCR instance to avoid reloading model

##### Configuration

- 📧 Support for custom `SMTP_HOST` and `SMTP_PORT` environment variables
- ✅ Added startup config validation with clear error messages

</details>

### Features

- Automated renewal of Euserv free VPS via GitHub Actions.
- Handles login, sessions, and **Two-Factor Authentication (2FA)**.
- **Triple-protection CAPTCHA solving**: local OCR (`ddddocr`) and TrueCaptcha API run **in parallel**, whichever succeeds first wins.
- Retrieves renewal PINs via **Cloud Mail API** (self-hosted mailbox, recommended) or **IMAP** (Gmail, etc.).
- Implements the complete and precise renewal workflow, including token exchange.
- Sends a run status report to your email after each execution.
- **Telegram Bot notifications** (optional): posts the run logs to Telegram via `TG_BOT_TOKEN` / `TG_USER_ID`.
- All credentials are managed securely via GitHub Secrets.

### Setup Guide

Please follow these steps carefully to get the workflow running.

#### Prerequisites

1. An active **Euserv Free VPS** account.
2. A mailbox to receive the renewal PIN. **One of the following**:
   - **Cloud Mail (recommended)**: a self-hosted [Cloud Mail](https://github.com/maillab/cloud-mail) (Cloudflare-based) instance; PINs are read via its HTTP API, no IMAP needed;
   - **or** any IMAP-capable mailbox (e.g., Gmail) with an **App Password** generated for it.
3. **(Optional)** A **TrueCaptcha** account (`apitruecaptcha.org`) as a parallel recognition channel alongside the local OCR.
4. A **GitHub account**.

#### Step 1: Fork the Repository

Click the **`Fork`** button at the top-right of this page to copy this project to your own GitHub account.

> **Security Recommendation**: ensure you have never accidentally committed personal credentials to the codebase. All sensitive values are injected via GitHub Secrets.

#### Step 2: Configure GitHub Secrets

This is the most critical step. Navigate to your forked repository, go to `Settings` -> `Secrets and variables` -> `Actions`, and click `New repository secret` to add each of the following secrets:

| Secret Name               | Example Value                   | Description                                                                                                                                                             |
| ------------------------- | ------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `EUSERV_USERNAME`         | `your_euserv_username`          | Your username for EUserv.                                                                                                                                               |
| `EUSERV_PASSWORD`         | `your_euserv_password`          | Your password for EUserv.                                                                                                                                               |
| `EUSERV_2FA`              | `ABCD1234EFGH5678`              | **(Optional)** The **Setup key** you get when enabling 2FA in your Euserv account.                                                                                      |
| `CAPTCHA_USERID`          | `your_captcha_userid`           | **(Optional)** Your `userid` from TrueCaptcha, used in parallel with the local OCR.                                                                                        |
| `CAPTCHA_APIKEY`          | `xxxxxxxxxxxxxxxxxxxx`          | **(Optional)** Your `apikey` from TrueCaptcha, used in parallel with the local OCR.                                                                                         |
| `EMAIL_HOST`              | `imap.gmail.com`                | Your email provider's IMAP server (optional if using Cloud Mail API).                                                                                   |
| `EMAIL_USERNAME`          | `your_email@gmail.com`          | Your full email address (admin account email in Cloud Mail mode).                                                                                        |
| `EMAIL_PASSWORD`          | `abcd efgh ijkl mnop`           | Your email **App Password** (admin mailbox password in Cloud Mail mode).                                                                                 |
| `CLOUD_MAIL_API_URL`      | `https://your-mail-root.example.com` | **(Optional)** The API URL of your self-hosted Cloud Mail. When set, the script fetches the PIN via the Cloud Mail API instead of IMAP.                    |
| `NOTIFICATION_EMAIL`      | `your_notify_email@example.com` | The email address to receive status reports.                                                                                                                            |
| `SMTP_USERNAME`           | `user@163.com`                  | **(Optional)** SMTP login account (sender). Falls back to `EMAIL_USERNAME`; set explicitly when using Cloud Mail mode.                                                   |
| `SMTP_PASSWORD`           | `smtp-auth-code`                 | **(Optional)** SMTP password/app-password matching `SMTP_USERNAME`. Same fallback rule as above.                                                                           |
| `SMTP_HOST`               | `smtp.gmail.com`                | **(Optional)** Manually specify SMTP server. Infers from IMAP if not provided.                                                                                          |
| `SMTP_PORT`               | `587`                           | **(Optional)** Manually specify SMTP port. Defaults to 587.                                                                                                             |
| `TG_BOT_TOKEN`            | `123456:ABC-DEF...`             | **(Optional)** Telegram Bot Token. When set, the run report is also pushed to Telegram (see "Telegram notifications" below).                                           |
| `TG_USER_ID`              | `123456789`                     | **(Optional)** Telegram user/group ID to receive the message.                                                                                                         |
| `TG_API_HOST`             | `https://api.telegram.org`      | **(Optional)** Telegram API host (default official; change for self-hosted proxies).                                                                                     |
| `PAT_WITH_WORKFLOW_SCOPE` | `github_pat_xxxx`               | **(Recommended)** [Fine-grained PAT](https://github.com/settings/personal-access-tokens/new) for dynamic scheduling. Permissions: `Contents` (RW) and `Workflows` (RW). |

**Ensure the secret names are copied exactly and replace the example values with your own real information.**

> **About 2FA**: It is highly recommended to enable 2FA in your Euserv account. Not only does it significantly improve your account security, but it may also cause the server to trust your login and **skip the image CAPTCHA**, saving you API costs.

> **Good to know**:
> - **Login CAPTCHAs and the renewal PIN are two different things.** At login you may face an image CAPTCHA (math expression) or a 2FA code (Authenticator, generated locally from the `EUSERV_2FA` Setup key via TOTP). The renewal PIN arrives by email (subject `EUserv - PIN for the Confirmation of a Security Check`) and is read by the mailbox module (Cloud Mail API or IMAP). The two are independent.
> - With `EUSERV_2FA` configured, Euserv usually trusts your login and skips the image CAPTCHA, so `CAPTCHA_*` is rarely exercised; without 2FA the `ddddocr` + `CAPTCHA_*` dual channel comes into play.

#### Using Cloud Mail as your mailbox (recommended, no IMAP required)

If your Euserv account email is hosted on self-hosted [Cloud Mail](https://github.com/maillab/cloud-mail) (deployed to your own domain, root URL like `https://你的邮件根地址`), the script can read the renewal PIN via its HTTP API, with no IMAP protocol needed:

1. In the Cloud Mail dashboard confirm the **admin email** and password (used by the `genToken` call to exchange a token).
2. Make sure your **Euserv login email** exists as an **inbox user** in Cloud Mail so the PIN mail is delivered there.
3. Configure these secrets:
   - `EMAIL_USERNAME` = Cloud Mail **admin email**
   - `EMAIL_PASSWORD` = that admin mailbox password
   - `CLOUD_MAIL_API_URL` = your Cloud Mail deployment URL (e.g., `https://your-mail-root.example`)
4. At runtime the script: calls `genToken` → queries `emailList` (filters `no-reply@euserv.com`, `type=0` inbox, `timeSort=desc`) → client-side exact match on subject `PIN for the Confirmation of a Security Check` → picks the newest by `createTime` → extracts the 6-digit PIN.

> **Note**: the script exact-matches the renewal-specific PIN subject, so other PIN mails (e.g., Email Validation) are ignored to avoid using the wrong PIN.

> If `CLOUD_MAIL_API_URL` is not set, the script falls back to IMAP; `EMAIL_HOST` is then required (e.g., `imap.gmail.com`).

**Quick reference for the two mailbox modes**

| Secret | Cloud Mail mode (recommended) | IMAP mode |
| --- | --- | --- |
| `EMAIL_HOST` | leave empty | `imap.gmail.com` |
| `EMAIL_USERNAME` | Cloud Mail **admin** email | your full mailbox address |
| `EMAIL_PASSWORD` | admin mailbox password | your **App Password** |
| `CLOUD_MAIL_API_URL` | required (e.g. `https://your-mail-root.example.com`) | leave empty |

#### Telegram notifications (optional)

To also receive the run report in Telegram (instead of, or alongside, the email report):

1. Create a bot with [@BotFather](https://t.me/BotFather) and copy the `TG_BOT_TOKEN` (e.g. `123456:ABC-DEF...`).
2. Private-message your bot once (or `@` it in a group), then ask [@userinfobot](https://t.me/userinfobot) for your numeric `TG_USER_ID`.
3. Set the secrets `TG_BOT_TOKEN` and `TG_USER_ID` (**optional**: `TG_API_HOST` for self-hosted proxies).
4. At the end of a run (or on config errors), `send_telegram_notification()` posts the full log to your Telegram as HTML.

> Long logs are truncated to about 4000 chars with a "(日志过长已截断)" marker.

#### Renewing multiple accounts (optional)

To manage **several Euserv accounts** with the same repository, **no new variables are needed** — put comma-separated values in the same environment variables:

**The short version:**
- **Accounts differ** (username / password / 2FA) → always comma-separated, aligned by position.
- **Mailbox service is shared** (one Cloud Mail instance / one IMAP server) → fill the mailbox secrets **once**; every account inherits them.
- **Mailbox services differ** (account 1 = IMAP, account 2 = Cloud Mail) → see the dedicated mixing example below; it needs placeholder slots.

| Secret | Single account | Multi-account, shared mailbox service |
|---|---|---|
| `EUSERV_USERNAME` | `user1@example.com` | `user1@example.com,user2@example.com` |
| `EUSERV_PASSWORD` | `pw1` | `pw1,pw2` |
| `EUSERV_2FA` | `KEY1` | `KEY1,KEY2` |
| `EMAIL_USERNAME` | `admin@mail.example` | `admin@mail.example` (shared, fill once) |
| `EMAIL_PASSWORD` | `mpw` | `mpw` (shared, fill once) |
| `CLOUD_MAIL_API_URL` | `https://mail.example` | `https://mail.example` (shared, fill once) |
| `EMAIL_HOST` (IMAP mode) | `imap.gmail.com` | `imap.gmail.com` (shared, fill once) |

> When should `EMAIL_USERNAME/PASSWORD/CLOUD_MAIL_API_URL/EMAIL_HOST` hold multiple values too? **Only when each account genuinely has a different mailbox of its own** (its own Cloud Mail admin / its own IMAP inbox). In almost all cases they are shared, so fill them once.

**Trigger**: as soon as `EUSERV_USERNAME` contains a comma, multi-account mode is enabled; without a comma the script behaves exactly as before (single account).

**Reporting & scheduling**: after all accounts finish, the email/Telegram report is **sent once as a summary**; the cron is set to the **earliest** next-renewal date across all accounts; if any account fails the whole run fails (triggering the retry).

##### Example ①: two accounts sharing one mailbox service

Both accounts are on the **same** Cloud Mail instance (or the same IMAP server):

```
EUSERV_USERNAME    = user1@example.com,user2@example.com   # position-based
EUSERV_PASSWORD    = pw1,pw2
EUSERV_2FA         = KEY1,KEY2
EMAIL_USERNAME     = admin@mail.example       # shared, fill once
EMAIL_PASSWORD     = mpw
CLOUD_MAIL_API_URL = https://mail.example     # shared, fill once
EMAIL_HOST         =                          # empty in Cloud Mail mode
```

##### Example ②: mixing — account 1 uses IMAP, account 2 uses Cloud Mail

Here the mailbox services **differ**: account 1 reads the PIN from its own IMAP inbox, account 2 via Cloud Mail API (a different admin credential). Key: `EMAIL_USERNAME` / `EMAIL_PASSWORD` must hold **two position-matched values** (the IMAP mailbox ≠ the Cloud admin), and the url/host slots must be written explicitly:

```
EUSERV_USERNAME    = user1@example.com,user2@example.com
EUSERV_PASSWORD    = pw1,pw2
EUSERV_2FA         = KEY1,KEY2
EMAIL_HOST         = imap.gmail.com,           # account 1 = IMAP; account 2 has no host (uses Cloud)
CLOUD_MAIL_API_URL = ,https://mail.example   # account 1 has no Cloud URL (uses IMAP); account 2 uses Cloud
EMAIL_USERNAME     = imap-mailbox@outlook.com,admin@mail.example   # by position: IMAP inbox, Cloud admin
EMAIL_PASSWORD     = imap_app_pw,cloud_mpw
```

> If you only fill one `EMAIL_USERNAME` (e.g. just the IMAP mailbox), it is **broadcast to every account** — account 2 would then try to log into Cloud Mail with the IMAP credentials and fail. In a mixed setup you must provide two different values by position.

#### Step 3: Manually Run the Workflow to Test

1. Go to the **`Actions`** tab in your repository.
2. Select the **`Euserv VPS Renewal`** workflow from the sidebar.
3. Click the **`Run workflow`** button to trigger a manual run.
4. Open the running job and watch the live logs. Look for:
   - `登录成功` (login succeeded, or CAPTCHA / 2FA being handled);
   - `正在访问服务器列表页面` and `发现 N 台服务器` (server contracts found);
   - when a renewal is due, `成功获取续期Token` plus a PIN (only the last 2 characters are logged for security);
   - the 📅 `next renewal` date at the end.

By default, the script waits for **30 seconds** after requesting a PIN before checking your email. If you experience email delays, increase `WAITING_TIME_OF_PIN` at the top of `Euserv_Renewal.py` (e.g., set it to `60`). In Cloud Mail mode you can also adjust `EMAIL_CHECK_INTERVAL` for polling frequency.

#### Troubleshooting

| Symptom | Likely fix |
| --- | --- |
| `必要的配置未设置` in the log | A required Secret is missing or misspelled. Double-check names (exact match) and that your mailbox mode has all the right values. |
| 登录失败次数过多 (login failing) | Check `EUSERV_USERNAME` / `EUSERV_PASSWORD`. If CAPTCHA repeats, inspect `CAPTCHA_*`, or enable 2FA to skip the CAPTCHA. |
| `无法获取 PIN` (cannot get PIN) | Cloud Mail mode: make sure `EMAIL_USERNAME` / `EMAIL_PASSWORD` are the **admin** account and `genToken` returns code 200. IMAP mode: verify the App Password and `EMAIL_HOST`. |
| Report email never arrives | In Cloud Mail mode set `SMTP_USERNAME` / `SMTP_PASSWORD` (a real sending mailbox + app/auth code) and `SMTP_HOST` explicitly — `EMAIL_*` are the Cloud Mail admin credentials, not SMTP ones, and SMTP host is never inferred without `EMAIL_HOST`. |
| Every run reports "skipped" | Normal — the renewal window has not opened yet. The dynamic scheduler always re-schedules the next run on the due date. |

### Schedule Configuration

The script uses a **dynamic scheduling mechanism**:

| Feature          | Description                                                                     |
| ---------------- | ------------------------------------------------------------------------------- |
| Dynamic Schedule | Automatically updates cron to next renewal date after completion, zero overhead |
| Retry on Failure | Retries every 30 minutes on failure, up to 3 times                              |
| Cross-day Retry  | Automatically retries the next day if all attempts fail                         |
| PAT Required     | Requires `PAT_WITH_WORKFLOW_SCOPE` Secret for dynamic scheduling                |

Create PAT: [Create Fine-grained Token](https://github.com/settings/personal-access-tokens/new)

1. **Repository access**: Select `Only select repositories` -> Select this repository
2. **Permissions**: Set `Contents` to **Read and write**, `Workflows` to **Read and write**

### License

This project is licensed under the **GNU General Public License v3.0**. See the `LICENSE` file for details.

### Disclaimer

- This project is provided "as is". The author is not responsible for any loss of service, data, or other damages that may result from its use.
- EUserv may change its website structure or renewal process at any time, which could break this automation.
- Use at your own risk.
