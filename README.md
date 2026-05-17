# Modular Timer Desktop

一个本地运行的多用途计时器，面向辩论赛、课堂展示、面试练习、考试模拟和专注学习。

它不是一个只能倒计时的小玩具，而是把计时流程拆成可组合的 **计时单元**：

- 单独计时：适合学习、演讲、面试、考试练习。
- 正方单元：只为正方计时。
- 反方单元：只为反方计时。
- 正反方同时：双方独立倒计时，可设置不同时间。
- 公共/单人单元：适合评委点评、中场休息、准备时间、普通计时。

## 功能

- 美观的桌面应用界面，基于 PySide6。
- 支持单独计时模式。
- 支持辩论会/流程计时模式。
- 支持添加、编辑、删除、上移、下移计时单元。
- 支持导入/导出 JSON 流程文件。
- 本地自动保存流程配置。
- 支持提示音开关。
- 支持快捷键：
  - 空格：开始/暂停
  - Enter：下一阶段
  - R：重置

## 本地运行

先安装依赖：

```bash
pip install -r requirements.txt
```

运行：

```bash
python run.py
```

## Windows 打包为 exe

在项目根目录打开 PowerShell，运行：

```powershell
.\build_windows.ps1
```

打包完成后，程序在：

```text
dist\ModularTimer\ModularTimer.exe
```

## 项目结构

```text
modular_timer_desktop/
├─ assets/
│  └─ app.ico
├─ src/
│  └─ modular_timer_desktop/
│     ├─ __init__.py
│     ├─ __main__.py
│     ├─ app.py
│     └─ settings.py
├─ run.py
├─ requirements.txt
├─ build_windows.ps1
├─ README.md
├─ LICENSE
└─ .gitignore
```

## 配置保存位置

程序会把自定义流程保存到当前用户目录下：

```text
~/.modular_timer_desktop/stages.json
```

删除这个文件即可恢复初始状态。

## 设计原则

核心不是“多几个按钮”，而是让每个计时环节都成为可复用模块。这样同一个程序可以服务于辩论赛、课堂展示、面试练习、社团活动、考试模拟，而不是锁死在某一个固定场景里。
