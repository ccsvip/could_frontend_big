# Windows 终端编码修复说明

> 适用于本仓库（`could_frontend_big`）在 Windows 下出现的三类乱码/刷屏问题。
> 这些是**宿主侧 / git 侧**问题，容器内 Python 本来就是 UTF-8（Python 3.13 在
> C/POSIX locale 下由 PEP 540 自动启用 UTF-8 mode 兜底），不必动 compose。
> 下面分三块，按需执行。**带 `git config` 的命令请你自己跑**，本仓未替你执行。

---

## 1. cmd 里中文 / traceback / `docker compose logs` 乱码

根因：宿主 **cmd 的活动代码页是 936 (GBK)**，不是 65001 (UTF-8)。任何把 UTF-8
字节写进 cmd 的来源（git 输出文件内容、容器透传的 UTF-8 日志、宿主直接跑的
Python 打印中文）都会被 cmd 按 GBK 解码 → 乱码。这是**纯显示层**问题，不会改写
磁盘文件。

### 临时（当前窗口生效）

```cmd
chcp 65001
```

切到 UTF-8 代码页后，再跑 `docker compose logs`、`git log` 等即可正常显示中文。
关掉窗口失效。

### 永久（推荐其一）

- **换终端**（最省事）：改用 **Windows Terminal** / **PowerShell 7** /
  **git-bash**，它们默认 UTF-8，不需要 `chcp`。
- **系统级 UTF-8**：`设置 → 时间和语言 → 语言和区域 → 管理语言设置 →
  「管理」选项卡 → 更改系统区域设置 → 勾选「Beta: 使用 Unicode UTF-8
  提供全球语言支持」`，重启。注意这是系统级改动，个别老旧 GBK 程序可能受影响。

---

## 2. 中文文件名被显示成 `\xxx` 八进制转义

根因：**git `core.quotepath` 取默认值 true**，遇到非 ASCII 文件名就转义。
关掉即可（你自己执行，本仓不替你改 git config）：

```cmd
git config --global core.quotepath false
```

执行后 `git status` / `git log` 等会直接显示中文文件名（前提是终端代码页已是
UTF-8，见第 1 节）。

---

## 3. `git add` 一直刷 `LF will be replaced by CRLF`

根因：`core.autocrlf=true`（global+system 生效）且此前仓库**无 `.gitattributes`**，
每个含 LF 的文本文件在 add/checkout 时都被提示行尾转换。无害，但持续刷屏。

**已处理**：仓库根已新增 `.gitattributes`（`* text=auto eol=lf` + 二进制类型标
`binary`），统一以 LF 入库/检出，且 `.gitattributes` 优先级高于 `core.autocrlf`，
刷屏会消失，无需再改 git config。

> 若你仍想让全局 git 行为一致（可选，且 `.gitattributes` 已优先生效，非必需）：
>
> ```cmd
> git config --global core.autocrlf input
> ```
>
> 含义：提交时把 CRLF 转成 LF、检出时不强转 CRLF。仓库有 `.gitattributes` 时
> 以后者为准。

---

## 4. 宿主直接跑 Python（非容器）时 traceback 乱码（可选）

只有在**宿主**而非容器里直接跑 Python 才需要。设以下用户环境变量（PowerShell
示例，永久写入用户级）：

```powershell
[Environment]::SetEnvironmentVariable("PYTHONUTF8", "1", "User")
[Environment]::SetEnvironmentVariable("PYTHONIOENCODING", "utf-8", "User")
```

容器内无需此项——已由 Python PEP 540 兜底为 UTF-8。

---

## 不在本说明范围

- `backend/apps/resources/serializers.py` 里若有「璇ラ煶鑹...」式乱码字符串，
  那是**历史落盘损坏的文件内容**（UTF-8 字节被当 GBK 解码再存回），与终端显示
  无关，由另一处流程单独修复，本说明不涉及。
