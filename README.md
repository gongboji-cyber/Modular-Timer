# ModularTimer

**ModularTimer** 是一款高度自由的本地桌面流程计时器，面向 PPT 汇报、课堂展示、辩论赛、答辩、面试训练、考试模拟和活动控场等场景。

它不是普通倒计时，也不是写死流程的辩论计时器。新版核心模型是：

```text
Flow → Stage → TimerUnit
流程 → 阶段 → 计时模块
```

每个流程可以包含多个阶段，每个阶段可以包含任意数量的计时模块；模块名称、模块数量、模块时长、模块颜色、铃声模式都可以自定义。

## 解决的痛点

很多学习、汇报、辩论、面试和活动场景并不是一个简单倒计时就能解决的，而是由多个阶段、多个角色和多个并行时间组成。普通计时器只能倒数，辩论计时器又过于固定，PPT 自带计时功能也不够灵活。本工具通过自由流程设计、多模块并行计时、PPT 悬浮显示和自定义铃声，让用户可以为任何复杂场景快速搭建专属计时流程。

## 功能

- 单独计时模式：适合专注学习、演讲练习、面试模拟、考试训练。
- 自由流程模式：自定义流程、阶段、模块数量、模块名称、模块时长。
- 多模块计时：支持单计时、并行计时、手动独立计时、依次计时。
- PPT 悬浮模块：无边框、置顶、可调透明度、可拖动、可锁定。
- 自定义铃声：支持静音、结束响铃、最后 10 秒提示、30/10 秒提示、结束循环响铃。
- 自定义本地铃声文件：建议优先使用 `.wav`，也可尝试 `.mp3` / `.ogg`。
- 流程导入/导出 JSON：方便不同活动模板复用。
- 本地自动保存：配置保存在用户本机，不需要账号、不需要后端。

## 本地运行

```powershell
cd "D:\新建文件夹\modular_timer_desktop"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py
```

如果 PowerShell 阻止脚本运行，先执行：

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## 打包成 Windows EXE

```powershell
cd "D:\新建文件夹\modular_timer_desktop"
.\build_windows.ps1
```

打包完成后打开：

```text
D:\新建文件夹\modular_timer_desktop\dist\ModularTimer\ModularTimer.exe
```

## 快捷键

| 快捷键 | 功能 |
|---|---|
| Space | 开始 / 暂停当前计时 |
| Enter | 下一阶段 |
| R | 重置当前计时 |
| Ctrl + L | 锁定 / 解锁 PPT 悬浮窗 |

## JSON 流程格式示例

```json
{
  "schema": "modular-timer-flow-v2",
  "name": "课堂辩论流程",
  "stages": [
    {
      "name": "自由辩论",
      "mode": "parallel",
      "timers": [
        { "name": "正方", "duration": 240, "color": "#2563EB", "alarm_mode": "global" },
        { "name": "反方", "duration": 240, "color": "#DC2626", "alarm_mode": "global" }
      ]
    },
    {
      "name": "PPT 汇报",
      "mode": "sequential",
      "timers": [
        { "name": "汇报", "duration": 480, "color": "#7C3AED", "alarm_mode": "last_10" },
        { "name": "提问", "duration": 180, "color": "#D97706", "alarm_mode": "end_once" }
      ]
    }
  ]
}
```

## 项目结构

```text
modular_timer_desktop/
├─ run.py
├─ requirements.txt
├─ build_windows.ps1
├─ assets/
│  └─ app.ico
├─ src/
│  └─ modular_timer_desktop/
│     ├─ __init__.py
│     ├─ __main__.py
│     ├─ app.py
│     └─ settings.py
└─ .github/
   └─ workflows/
      └─ build-windows.yml
```

## License

MIT
