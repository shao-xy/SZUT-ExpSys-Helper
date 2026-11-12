> **使用前请先读本节。**
>
> 1. **实验系统地址：<http://10.28.203.178/index2.aspx>**
>    站点在校园网内，不在校内请先连学校 VPN。
>    浏览器打不开时，先连 VPN，再运行 `labreg preflight` 测连通性。
> 2. 本工具只覆盖排课环节。**课程大纲与实验任务书必须由教师本人在系统中手工提交**，
>    工具不会代做，也无法代做。任务书未提交时，工具会终止并提示。
> 3. 首次使用按「五分钟上手」执行：`labreg init` → 填 `.env` 与 `configs/courses.yaml`
>    → `labreg selftest` → `labreg preflight` → `labreg run --dry-run` → `labreg run`。
> 4. 排课计划 `configs/courses.yaml` 含个人教学信息，默认不入库。
>
---

# labreg · 实验系统排课工具

面向实验教学管理系统的**课程排课自动化工具**。教师用一份 YAML 描述
「每门课程、每个班级、每个实验在哪几周、星期几、第几节、在哪个机房」，
工具负责登录站点并逐条落实确认学生、学生分批与课表安排。

纯命令行，无 GUI、无浏览器依赖，几十秒完成一学期的排课。

---

## 站点地址

**实验教学管理系统**：[http://10.28.203.178/index2.aspx](http://10.28.203.178/index2.aspx)

> 站点位于校园网内，不在校内请先连接学校 VPN。
> 浏览器打不开时，先连 VPN，再用 `labreg preflight` 测一下连通性。

---

## 它做什么

| 步骤 | 内容 | 谁来做 |
| --- | --- | --- |
| ① 安排并提交课程大纲 | 教学内容、学时、学分 | **教师手工** |
| ② 提交实验任务书 | 各实验项目与周次 | **教师手工** |
| ③ 确认学生 | 把匹配班级的学生导入实验项目 | 工具 |
| ④ 学生分批 | 整班同时发下（批数可调） | 工具 |
| ⑤ 制定课表 | 周次、星期、节次、机房 | 工具 |

**①② 必须由教师本人在系统中手工完成**，工具不代做、不代填、不代提交。
这是教学管理决策，工具没有依据也不应代劳。
当任务书未提交时，工具会**主动终止**并给出人工操作指引。

---

## 安装

```powershell
git clone <仓库地址>
cd 实验系统助手

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

依赖：requests、python-dotenv、PyYAML、lxml、pycryptodome、ddddocr（验证码识别）。

## 五分钟上手

```powershell
# 1. 生成待填写的配置（.env 与 configs/courses.yaml）
labreg init

# 2. 编辑 .env：站点地址已预填，只需填账号与密码
#    编辑 configs/courses.yaml：填写课程、班级、周次、节次、机房

# 3. 本地自检：依赖、配置、计划是否就绪（不访问站点）
labreg selftest

# 4. 站点体检：网络、登录、任务书状态、计划与站点是否匹配
labreg preflight

# 5. 预演：确认学生 + 分批，但不提交排课
labreg run --dry-run

# 6. 执行排课
labreg run

# 7. 核对结果
labreg status
```

第 4 步会逐项报告。若「网络连通性」不通过，说明还没连校园网 VPN；
若「任务书状态」不通过，说明该课程尚未提交任务书 —— 请先在系统中
手工安排课程大纲并提交任务书，再回来重跑。

站点地址已预填为 `http://10.28.203.178/`，如与本校实际不同请在 `.env` 中修改。

---

## 定制方式：只改一个 YAML

排课计划全部写在 `configs/courses.yaml`，这是教师定制的唯一入口：

```yaml
courses:
  - name: 示例课程
    course_code: "00000000"
    classes:
      - name: 示例课程-0001A            # 必须与站点班级名完全一致
        weekday: 星期四
        start_period: 3                # 起始节次
        end_period: 4                  # 结束节次
        room: N0000                    # 机房号
        batches: 1                     # 学生分批数
        experiments:
          - project: 实验项目一          # 实验项目名关键字
            weeks: [1, 3]              # [起始周, 结束周]

          - project: 实验项目二
            weeks: [4, 7]
            weekday: 星期四            # 可覆盖班级默认值
            start_period: 3
            room: N0000
```

要点：

- `weeks` 是闭区间。`[1, 3]` 表示第 1、2、3 周**每周**都上课。
- 工具**只做每周排课**，不区分单双周——站点上「单周/双周」是另一套排法，
  工具不会去勾选，避免出现隔周上课。
- `project` 按名称包含关系匹配，写项目名的一部分即可。
- 机房用房号表示，工具自动解析出站点的实验室别名与机房编号。
- 同一课程的多个班级各自配置，可以有不同的星期、节次、机房。

字段完整说明见 [`labreg/templates/courses.yaml.template`](labreg/templates/courses.yaml.template)
（`labreg init` 生成的模板里也有同样注释）。

---

## 让 Agent 帮你写排课计划

`configs/courses.yaml` 字段不多，但手写容易出错：周次是闭区间还是离散周、
星期与节次怎么对应、机房该写房号还是站点上的完整文本。

装上 Agent Skill 后，让 Agent 按你的自然语言描述生成最省事。

```powershell
labreg install-skill -d .trae/skills     # Trae
labreg install-skill -d .claude/skills   # Claude Code
```

然后把下面这段提示词发给 Agent，把 `<>` 里的内容换成你的实际情况：

```text
请帮我生成实验排课计划文件 configs/courses.yaml。

我的课程安排如下：
- 课程名称：<课程名称>
- 课程代码：<课程代码>
- 班级一：<班级名>，<星期几> <起始节次>-<结束节次> 节，机房 <房号>
- 班级二：<班级名>，<星期几> <起始节次>-<结束节次> 节，机房 <房号>

实验项目与周次（每周都上课，不区分单双周）：
- <实验项目名>：第 <起始周> 周 到 第 <结束周> 周
- <实验项目名>：第 <起始周> 周 到 第 <结束周> 周

要求：
1. 先运行 `labreg courses` 取得站点上的真实班级名与实验项目名，以站点名称为准；
   我写的名称如与站点不一致，请在生成前告诉我。
2. 周次写成闭区间。例如 weeks: [1, 3] 表示第 1、2、3 周每周都上课，
   不是只在第 1 周和第 3 周上课。
3. 不要填单双周，工具只做每周排课。
4. 只生成这一个 YAML 文件。课程大纲与实验任务书由我本人在系统中手工提交，
   你不要代填、不要代写、不要代提交。
5. 生成后运行 `labreg plan` 自检，把结果给我看。
```

Agent 生成后，建议你自己再核对三点：

- `weeks` 是不是写成了闭区间，而不是「第 1、3 周」这种离散写法；
- 班级名与实验项目名是否与站点上的完全一致（`labreg courses`、`labreg status` 可查）；
- 机房只写房号（站点文本中方括号前的部分），不要写 `N0000[校区-楼栋-房号]`。

最后用 `labreg preflight` 确认计划与站点匹配，`labreg run --dry-run` 预演一遍再执行。

---

## 命令

| 命令 | 作用 | 是否写站点 |
| --- | --- | --- |
| `labreg init` | 生成 `.env` 与 `configs/courses.yaml` 模板 | 否 |
| `labreg selftest` | 本地自检：依赖 / 配置 / 计划 | 否 |
| `labreg check` | 检查本地配置 | 否 |
| `labreg plan` | 展示排课计划 | 否 |
| `labreg preflight` | 检查网络 / 登录 / 任务书 / 计划匹配 | 否（只读） |
| `labreg courses` | 列出站点可排课班级 | 否（只读） |
| `labreg status` | 查看各实验当前状态 | 否（只读） |
| `labreg run --dry-run` | 预演：确认学生 + 分批 | 是（分批） |
| `labreg run` | 执行排课 | 是 |
| `labreg clear --dry-run` | 列出待清除的排课 | 否（只读） |
| `labreg clear` | 清除已有排课 | 是（删除） |
| `labreg install-skill` | 安装 Agent Skill | 否 |
| `labreg sync-skill` | 同步仓库内 Skill | 否 |

常用参数：

```powershell
labreg run --dry-run          # 只做确认与分批，不提交排课
labreg run --force            # 存在冲突时仍然提交
labreg run --skip-confirm     # 跳过确认学生
labreg run --skip-group       # 跳过学生分批
labreg status -k "示例课程-0001A"   # 只看某个班级
labreg clear -k "示例课程-0001A" --dry-run
labreg -v run                 # 输出调试日志
```

**`run` 是幂等的**：已存在相同安排的实验会自动跳过，可安全重复执行。

### JSON 输出

`plan`、`selftest`、`preflight`、`courses`、`status`、`clear`、`run`
均支持 `--json`，输出结构化结果，便于脚本或 Agent 直接解析：

```powershell
labreg status --json
labreg preflight --json
labreg run --json
```

退出码：`0` 全部成功，`1` 有失败项或前置检查未通过。

---

## 给 Agent 用

本工具带一个 Agent Skill，装上后 Agent 就能按既定流程操作：

```powershell
labreg install-skill -d .claude/skills     # Claude Code
labreg install-skill -d .trae/skills       # Trae
```

Skill 内容随包分发（`labreg/skill/SKILL.md`），包含完整的操作流程、
排课计划写法、命令速查与故障排查。

Skill 里明确写死了两条红线：

1. **课程大纲与任务书必须由教师手工完成，Agent 不得代劳。**
2. 任务书未提交时立即停止并请教师处理，不得自行提交。

---

## 排完是什么样

站点**每周生成一条记录**。第 1-3 周排课会产生第 1、2、3 周共 3 条记录。
这是正常结果，不是重复排课。`labreg status` 会逐条列出。

提交前站点会检查教师、学生、机房三类冲突。工具默认**发现冲突就不提交**
并报告原因，确认可以强排时用 `--force`。

---

## 目录结构

```
.
├─ labreg/                  # 主包
│  ├─ cli.py                # 命令行入口
│  ├─ client.py             # 会话、登录（验证码自动识别）、隐藏域管理
│  ├─ crypto.py             # 站点密码加密（AES-CBC）
│  ├─ pages.py              # 页面解析
│  ├─ workflow.py           # 排课三步流程
│  ├─ preflight.py          # 前置条件检查（含任务书提醒）
│  ├─ selftest.py           # 本地自检
│  ├─ scaffold.py           # 工作区脚手架、Skill 分发
│  ├─ output.py             # 文本 / JSON 双输出
│  ├─ config.py             # 配置加载
│  ├─ skill/SKILL.md        # Agent Skill 唯一来源
│  └─ templates/            # init 用的模板
├─ .trae/skills/labreg/     # Trae 加载的 Skill（由 sync-skill 同步）
├─ configs/courses.yaml     # 排课计划 ← 教师改这里
├─ docs/
│  ├─ 实验系统使用基本流程.md   # 站点的人工操作流程与责任划分
│  └─ 接口协议说明.md           # 逆向得到的接口与字段说明
├─ tests/                   # 离线回归测试（不联网）
├─ scripts/                 # 抓包逆向与现场探测工具
├─ var/                     # 本地产物，不入库
└─ pyproject.toml
```

## 开发

```powershell
pip install pytest
pytest tests -q          # 19 项离线测试，不访问站点
```

测试覆盖配置解析与覆盖规则、页面解析、幂等与冲突判定逻辑。
站点协议若发生变化，先跑测试看是否失效，再更新 `docs/接口协议说明.md`。

## 安全约定

- `.env`、`*.har`、`var/` 已在 `.gitignore` 中，不进入版本库。
- 凭据只从本地 `.env` 读取，代码中无硬编码口令。
- 配置文件查找顺序：`LABREG_HOME` 环境变量 → 当前目录 → 源码根目录，
  因此 pip 安装后可在任意目录通过 `labreg init` 建立自己的工作区。
- Skill 安装目录（`.claude/skills/` 等）不入库，由 `labreg install-skill` 生成。

## 文档

- [实验系统使用基本流程](docs/实验系统使用基本流程.md) —— 站点的人工操作流程与责任划分，工具按此实现
- [接口协议说明](docs/接口协议说明.md) —— 接口、字段、级联关系、坑位说明
- [分发指南](docs/分发指南.md) —— 发给同事或发布到 GitHub 的做法与脱敏说明

## 分发给其他教师

```powershell
python scripts/build_release.py     # 生成 dist/labreg-release/
```

产物是一份**可直接使用、且不含任何凭据与个人数据**的干净副本：
不含 `.env`、不含个人排课计划、不含 Git 历史；站点地址已预填，对方解压即可用。
构建脚本会扫描全部文件，发现敏感内容即中止。

详见 [分发指南](docs/分发指南.md)。

## 安全约定

- `.env`、`*.har`、`var/` 已在 `.gitignore` 中，不进入版本库。
- 凭据只从本地 `.env` 读取，代码中无硬编码口令。
- 配置文件查找顺序：`LABREG_HOME` 环境变量 → 当前目录 → 源码根目录，
  因此 pip 安装后可在任意目录通过 `labreg init` 建立自己的工作区。
