---
name: "labreg"
description: "实验教学管理系统课程排课工具。以课程为单位批量确认学生、学生分批与安排实验课表。Invoke when 用户要求为实验课排课、制定实验课表、确认实验课学生、批量安排实验周次/节次/教室，或提到 labreg。"
---

# 实验系统排课工具（labreg）

## 这个工具做什么

`labreg` 面向实验教学管理系统（ASP.NET WebForms），把「确认学生 → 学生分批 → 制定课表」
三步重复操作自动化。教师只需用 YAML 描述**每门课程的每个班级每个实验在哪几周、星期几、第几节、在哪个机房**，
工具负责登录站点并逐条落实。

工具只写「排课」相关的数据，**不会**代替教师做课程级的事务。

## 硬性边界：以下两项必须由教师本人手工完成

> **安排并提交课程大纲、提交实验任务书——这两步必须由教师本人在系统中手工完成。
> 任何情况下都不要代替教师执行，也不要代填、代写、代提交。**

原因：这两项属于教学管理决策，涉及课程内容与教学承诺，工具没有依据也不应代劳。

若发现课程尚未提交任务书（站点「制订课表（整班排课）」页面为空），
**立即停止并请教师手工完成后再继续**，不要尝试自行提交任务书。

`labreg preflight` 会自动检测这一状态并给出上述指引。

## 工作流程

### 1. 先确认前置条件

```powershell
labreg preflight
```

逐项检查网络连通性（校园网/VPN）、登录、任务书状态、计划与站点是否匹配。
任何一项为「阻断」就停下来，把提示原样转达给教师，不要自行绕过。

### 2. 确认计划内容

```powershell
labreg plan          # 展示 configs/courses.yaml 中的计划
labreg status        # 查看站点上各班级各实验的当前状态
labreg courses       # 列出站点上可排课的班级
```

若计划中的班级名或实验项目名在站点上找不到，用 `labreg courses` / `labreg status`
取得站点上的**实际名称**，再修改 `configs/courses.yaml`。
匹配是按名称包含关系判断的，`project: 实验一` 可匹配站点上的「实验一 [课程代码01]」。

### 3. 预演

```powershell
labreg run --dry-run
```

完成确认学生与学生分批，但不提交排课。把预演结果告诉教师确认。

### 4. 执行

```powershell
labreg run
```

输出逐条报告每项操作结果。命令是**幂等**的：已存在相同安排会自动跳过，可安全重复执行。

### 5. 复核

```powershell
labreg status
```

核对每个实验的周次、星期、节次与地点是否与计划一致。

## 排课计划怎么写

计划写在 `configs/courses.yaml`，这是教师定制的唯一入口：

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
```

规则：

- `weeks` 是闭区间。`[1, 3]` 表示第 1、2、3 周**每周**都上课。
- 工具只做**每周**排课，不区分单双周——站点上「单周/双周」是另一套排法，
  本工具不会去勾选，避免出现隔周上课。
- 每个实验可以覆盖班级的默认星期/节次/机房。
- 机房用房号表示，工具自动解析出站点的实验室别名与机房编号。
- 新教师用 `labreg init` 生成带注释的模板。

## 命令速查

| 命令 | 作用 | 是否写站点 |
| --- | --- | --- |
| `labreg init` | 生成 `.env` 与 `configs/courses.yaml` 模板 | 否 |
| `labreg check` | 检查本地配置 | 否 |
| `labreg plan` | 展示排课计划 | 否 |
| `labreg preflight` | 检查网络/登录/任务书/计划匹配 | 否（只读） |
| `labreg courses` | 列出站点可排课班级 | 否（只读） |
| `labreg status` | 查看各实验当前状态 | 否（只读） |
| `labreg run --dry-run` | 预演：确认学生 + 分批 | 是（分批） |
| `labreg run` | 执行排课 | 是 |
| `labreg clear --dry-run` | 列出待清除的排课 | 否（只读） |
| `labreg clear` | 清除已有排课 | 是（删除） |
| `labreg install-skill` | 安装本 Skill | 否 |

## 给 Agent 的额外约定

`plan`、`preflight`、`courses`、`status`、`clear`、`run` 都支持 `--json`，
输出结构化结果，便于直接解析而非解析自然语言：

```powershell
labreg status --json      # {"items": [{class_name, project, confirmed, matched, ...}]}
labreg run --json         # {"passed": true, "failures": 0, "items": [...]}
labreg preflight --json   # {"passed": false, "checks": [{name, ok, detail, hint}]}
```

解析要点：

- `preflight` 的 `passed` 为 false 时，**先读 `checks[].hint`**，那是给人看的处置建议，
  按提示停下来请教师处理，不要自行绕过。
- `run` 的 `items[].step` 取值为 `locate` / `confirm` / `group` / `schedule`，
  `ok` 标识该项是否成功。
- 退出码：0 表示全部成功，1 表示有失败项或前置检查未通过。

执行排课前应先向教师展示 `labreg run --dry-run` 的结果并取得确认。
`labreg run` 本身幂等，重复执行不会产生重复排课。

## 排课是怎么落地的

对每个（班级 × 实验项目）依次执行三步：

1. **确认学生** —— 点「引用」，把匹配班级的学生全部导入
2. **学生分批** —— 全选学生，批数填 1（整班同时发下），点「确认分批」
3. **制定课表** —— 设置周次、星期、节次、机房，提交

第 3 步在站点上要分四次回发：选实验室别名 → 选起始节次 → 选结束节次 → 提交。
工具已按此顺序实现，**不要试图合并成一次请求**。

## 排完是什么样

站点**每周生成一条记录**。例如第 1-3 周排课会产生第 1、2、3 周共 3 条记录。
这是正常结果，不是重复排课。`labreg status` 会把每条记录逐行列出。

## 冲突处理

提交前站点会检查教师、学生、机房三类冲突。工具默认**发现冲突就不提交**，
并报告冲突原因。确认确实可以强排时，用 `labreg run --force`。

## 常见问题

| 现象 | 处理 |
| --- | --- |
| preflight 提示任务书未提交 | 请教师手工提交课程大纲与任务书，不要代做 |
| preflight 提示网络不可达 | 站点在校园网内，请连接学校 VPN |
| 提示班级/实验项目找不到 | 用 `labreg courses`、`labreg status` 取得站点实际名称后改计划 |
| 提示存在冲突 | 先看冲突原因；确需强排用 `--force` |
| 验证码识别失败 | 脚本会自动重试 3 次；持续失败请教师在浏览器手工登录一次排除干扰 |
