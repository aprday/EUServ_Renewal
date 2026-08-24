# EUserv Auto Renewal

通过 GitHub Actions 自动检查并续期 EUserv 服务器合同，支持图片验证码、邮箱 PIN、Gmail IMAP、TrueCaptcha 和 Telegram 通知。

本项目不是 EUserv 官方工具。EUserv 页面或续期流程变化时，自动化可能失效，请保留人工检查到期日期的习惯。

## 功能

- 每月 6 至 9 日每天检查一次合同状态
- 未到续期窗口时自动跳过
- 续期成功后保存下一次可续期日期，在对应月份前不再登录
- 6 至 8 日失败时通过 Telegram 报告原因并在次日重试
- 9 日仍失败时报告原因并暂停后续自动尝试，等待人工处理
- 本地 `ddddocr` 识别验证码
- 可选 TrueCaptcha API，提高验证码识别成功率
- 从 Gmail 或其他 IMAP 邮箱读取 EUserv 安全 PIN
- 保存受信任设备 Cookie，减少重复 PIN 验证
- 可选 Telegram 和 Bark 通知
- 支持多个 EUserv 账号
- 默认对公开 Actions 日志和通知中的账号、合同及安全数据进行脱敏

## 调度方式

默认工作流位于 `.github/workflows/renewal.yml`：

```yaml
- cron: '0 12 6-31 * *'
```

含义是每月 6 至 9 日，每天 UTC 12:00，也就是北京时间 20:00 最多检查一次。`renewal_state.json` 记录下一次可续期日期；未到对应月份时，工作流会在安装依赖和登录 EUserv 之前直接退出。脚本只有在页面明确出现 `Extend contract` 控件时才提交续期。

例如合同显示：

```text
Contract extension possible from 2026-09-09
```

则 9 月 6、7、8 日只检查不续期，9 月 9 日进入续期窗口后执行续期。成功后生成 `renewed_2026-09.txt`，并把新的可续期日期写入 `renewal_state.json`；在新日期所属月份之前不再登录 EUserv。

如果 9 日仍出现登录失败、合同读取失败、续期入口未开放或续期无法验证等错误，脚本会发送 Telegram 原因通知，并将 `renewal_state.json` 的 `status` 改为 `stopped`。此后自动任务不再登录，需人工排查后把状态改回 `waiting` 并填入正确的 `next_renewal_date`。

## 部署

1. 将本仓库复制到自己的私有仓库，或使用 GitHub 的 Import repository 功能。
2. 打开仓库 `Settings` → `Secrets and variables` → `Actions`。
3. 添加下表中的 Secrets。
4. 打开 `Actions` → `EUserv Auto Renewal` → `Run workflow`，首次手动验证。

### 必填 Secrets

| Secret | 说明 |
| --- | --- |
| `EUSERV_USERNAME` | EUserv 登录邮箱或客户 ID |
| `EUSERV_PASSWORD` | EUserv 登录密码 |
| `EUSERV_ORDER_IDS` | 允许续期的合同编号；多个编号用英文逗号分隔 |
| `EMAIL_USERNAME` | 接收 EUserv PIN 的邮箱地址 |
| `EMAIL_PASSWORD` | 邮箱应用专用密码；Gmail 请保留生成时的完整格式 |

脚本会根据邮箱域名推断 IMAP 地址。Gmail 使用 `imap.gmail.com`。

### 可选 Secrets

| Secret | 说明 |
| --- | --- |
| `CAPTCHA_USERID` | TrueCaptcha 用户 ID |
| `CAPTCHA_APIKEY` | TrueCaptcha API Key |
| `TG_BOT_TOKEN` | Telegram Bot Token |
| `TG_USER_ID` | Telegram chat ID |
| `TG_API_HOST` | Telegram API 地址，默认 `https://api.telegram.org` |
| `BARK_URL` | Bark 推送地址 |
| `MAX_LOGIN_RETRIES` | 登录重试次数，默认 `5` |
| `MAX_WORKERS` | 多账号并发数，默认 `3` |

## 多账号

第一个账号使用无后缀变量，后续账号依次增加数字：

| 账号 | 登录邮箱 | 登录密码 | PIN 邮箱 | 邮箱密码 |
| --- | --- | --- | --- | --- |
| 1 | `EUSERV_USERNAME` | `EUSERV_PASSWORD` | `EMAIL_USERNAME` | `EMAIL_PASSWORD` |
| 2 | `EUSERV_USERNAME2` | `EUSERV_PASSWORD2` | `EMAIL_USERNAME2` | `EMAIL_PASSWORD2` |
| 3 | `EUSERV_USERNAME3` | `EUSERV_PASSWORD3` | `EMAIL_USERNAME3` | `EMAIL_PASSWORD3` |

工作流默认只映射第一个账号。需要多账号时，请在 `.github/workflows/renewal.yml` 的 `env` 中增加对应 Secret 映射。

## TrueCaptcha

TrueCaptcha 是可选增强。配置 `CAPTCHA_USERID` 和 `CAPTCHA_APIKEY` 后，脚本优先调用：

```text
POST https://api.apitruecaptcha.org/one/gettext
```

API 失败时自动回退到本地 `ddddocr`，不会把 EUserv 登录 Cookie 发送给验证码服务。
发送给 TrueCaptcha 的只有验证码图片、`userid` 和 `apikey`。它能提高图片验证码识别成功率，但不能判断合同是否可续期，也不能替代邮箱 PIN。

## 安全建议

- 推荐使用私有仓库。
- 所有密码、Token 和 API Key 只存入 GitHub Actions Secrets，不要写进代码。
- GitHub Actions 日志仍可能因代码错误输出敏感数据，修改日志逻辑时要谨慎。
- Gmail 使用独立应用专用密码，不使用 Google 主密码。
- 定期轮换 EUserv 密码、邮箱应用密码、Telegram Token 和 GitHub Token。
- 不要运行来源不明的 Pull Request workflow；它可能尝试读取或外传 Secrets。

### 公开日志隐私

- EUserv 邮箱和 PIN 邮箱不会写入日志，账号显示为不可逆匿名标签，例如 `account-a1b2c3d4`。
- 合同编号不会写入日志或 `renewal_state.json`，合同显示为匿名标签，例如 `contract-e5f6a7b8`。
- 图片验证码内容、邮箱 PIN、登录会话标识和临时续期 Token 均不输出。
- 统一日志过滤器会再次遮盖环境变量中的账号、密码、API Key、Bot Token 和 PAT。
- Telegram/Bark 通知沿用相同的匿名账号和合同标签。
- 下一次可续期日期仍保存在 `renewal_state.json`，用于避免无意义登录；其中不保存账号或合同编号。

## 本地运行

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:EUSERV_USERNAME = "your-login"
$env:EUSERV_PASSWORD = "your-password"
$env:EMAIL_USERNAME = "your-pin-mailbox"
$env:EMAIL_PASSWORD = "your-app-password"
python euserv_renew.py
```

## 常见问题

### 登录返回空页面或重复失败

先确认 EUserv 网页端可以正常登录，然后检查账号是否临时锁定。当前实现基于持续可用的登录、验证码和邮箱 PIN 流程，不再调用旧版 `Euserv_Renewal.py`。

### 无法读取 Gmail PIN

- 确认使用应用专用密码。
- 确认接收 PIN 的邮箱与 `EMAIL_USERNAME` 一致。
- 检查 Google 账号安全页面中应用专用密码是否仍有效。

### Actions 成功但没有续期

Actions 成功只代表脚本正常执行。未到 `Contract extension possible from` 日期时，脚本会正常跳过。

## 项目来源

本项目在以下开源项目的实践基础上独立维护：

- [wimdaw/EUServ_Renewal](https://github.com/wimdaw/EUServ_Renewal)
- [Michaol/euserv-renewal-bot](https://github.com/Michaol/euserv-renewal-bot)
- [dufei511/euserv_py](https://github.com/dufei511/euserv_py)

当前续期主流程源自 `dufei511/euserv_py` 的 MIT 许可实现，并进行了 GitHub Actions、Secret 命名、TrueCaptcha、调度和通知适配。许可证与第三方声明见 `LICENSE` 和 `THIRD_PARTY_NOTICES.md`。

## 许可证

项目整体按 GPL-3.0-or-later 发布。第三方来源代码继续保留其原始版权与许可声明。
