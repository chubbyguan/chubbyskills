"""Install and inspect the OS timer that runs `subscribe tick`.

The subscription docs used to hand the reader a launchd plist containing four
absolute paths to substitute by hand, with the log directory never mentioned.
That is where the pipeline stopped being reproducible: the interpreter, the
entrypoint, the config path and the log paths are all machine-specific, and a
single wrong value produces a job that fails quietly every hour.

Generation is kept in pure functions so the unit files can be asserted on any
platform; only `install` / `uninstall` touch the system.
"""

from __future__ import annotations

import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = REPO_ROOT / "tools" / "chubby.py"

LAUNCHD_LABEL = "im.chubby.chubbyskills.subscribe"
SYSTEMD_SERVICE = "chubbyskills-subscribe.service"
SYSTEMD_TIMER = "chubbyskills-subscribe.timer"
DEFAULT_INTERVAL_MINUTES = 60
MAX_LOG_LINES = 5


class ScheduleError(RuntimeError):
    pass


def schedule_paths(args: Any, config: dict[str, Any]) -> dict[str, Any]:
    """Everything a generated unit needs, read from the running process.

    Resolving these here is the whole point: the user ran the command from the
    environment that works, so the timer should reproduce that environment
    rather than an absolute path they typed into a template.
    """
    config_path = config.get("_config_path")
    if not config_path:
        raise ScheduleError("无法确定配置文件路径，请先用 --config 指定")
    config_path = Path(config_path).expanduser().resolve()
    log_dir = config_path.parent / ".chubby" / "logs"

    command = [
        str(Path(sys.executable).resolve()),
        str(ENTRYPOINT),
        "--config",
        str(config_path),
        "subscribe",
    ]
    subscriptions = getattr(args, "subscriptions", "") or ""
    if subscriptions:
        command += ["--subscriptions", str(Path(subscriptions).expanduser().resolve())]
    command += ["tick", "--due", "--process-limit", str(getattr(args, "process_limit", 3) or 3)]

    return {
        "config_path": config_path,
        "log_dir": log_dir,
        "tick_log": config_path.parent / ".chubby" / "tick-log.jsonl",
        "command": command,
        "python": command[0],
    }


def build_launchd_plist(paths: dict[str, Any], *, interval_minutes: int) -> str:
    label = LAUNCHD_LABEL
    arguments = "\n".join(f"    <string>{item}</string>" for item in paths["command"])
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>{label}</string>
  <key>ProgramArguments</key><array>
{arguments}
  </array>
  <key>StartInterval</key><integer>{interval_minutes * 60}</integer>
  <key>StandardOutPath</key><string>{paths['log_dir'] / 'subscribe.out.log'}</string>
  <key>StandardErrorPath</key><string>{paths['log_dir'] / 'subscribe.err.log'}</string>
</dict></plist>
"""


def build_systemd_units(paths: dict[str, Any], *, interval_minutes: int) -> dict[str, str]:
    service = f"""[Unit]
Description=chubbyskills subscription tick

[Service]
Type=oneshot
ExecStart={' '.join(paths['command'])}
StandardOutput=append:{paths['log_dir'] / 'subscribe.out.log'}
StandardError=append:{paths['log_dir'] / 'subscribe.err.log'}
"""
    timer = f"""[Unit]
Description=Run the chubbyskills subscription tick on a timer

[Timer]
OnBootSec={interval_minutes}min
OnUnitActiveSec={interval_minutes}min
Persistent=true

[Install]
WantedBy=timers.target
"""
    return {SYSTEMD_SERVICE: service, SYSTEMD_TIMER: timer}


def launchd_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{LAUNCHD_LABEL}.plist"


def systemd_dir() -> Path:
    return Path.home() / ".config" / "systemd" / "user"


def install(args: Any, config: dict[str, Any]) -> int:
    requested = getattr(args, "interval_minutes", None)
    interval = DEFAULT_INTERVAL_MINUTES if requested is None else int(requested)
    if interval < 5 or interval > 1440:
        raise ScheduleError("--interval-minutes 需在 5 到 1440 之间")
    paths = schedule_paths(args, config)
    # The docs never mentioned this directory, which is one of the reasons a
    # hand-edited unit failed with no visible error.
    paths["log_dir"].mkdir(parents=True, exist_ok=True)

    system = platform.system()
    if system == "Darwin":
        target = launchd_path()
        content = build_launchd_plist(paths, interval_minutes=interval)
        if getattr(args, "dry_run", False):
            print(content)
            print(f"（--dry-run：未写入 {target}）")
            return 0
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        subprocess.run(
            ["launchctl", "bootout", f"gui/{_uid()}/{LAUNCHD_LABEL}"],
            capture_output=True,
            text=True,
        )
        loaded = subprocess.run(
            ["launchctl", "bootstrap", f"gui/{_uid()}", str(target)],
            capture_output=True,
            text=True,
        )
        print(f"✅ 已写入：{target}")
        if loaded.returncode != 0:
            print(f"❌ 加载失败：{loaded.stderr.strip() or loaded.stdout.strip()}")
            return 1
        print(f"✅ 已加载：每 {interval} 分钟执行一次")
        print(f"   解释器：{paths['python']}")
        print(f"   日志：{paths['log_dir']}")
        print("   查看状态：subscribe schedule status")
        return 0

    if system == "Linux":
        directory = systemd_dir()
        units = build_systemd_units(paths, interval_minutes=interval)
        if getattr(args, "dry_run", False):
            for name, content in units.items():
                print(f"--- {directory / name}")
                print(content)
            print("（--dry-run：未写入）")
            return 0
        directory.mkdir(parents=True, exist_ok=True)
        for name, content in units.items():
            (directory / name).write_text(content, encoding="utf-8")
            print(f"✅ 已写入：{directory / name}")
        enable = subprocess.run(
            ["systemctl", "--user", "enable", "--now", SYSTEMD_TIMER],
            capture_output=True,
            text=True,
        )
        if enable.returncode != 0:
            print("⚠️  未能自动启用，请手动执行：")
            print(f"   systemctl --user enable --now {SYSTEMD_TIMER}")
        else:
            print(f"✅ 已启用：每 {interval} 分钟执行一次")
        print("   查看状态：subscribe schedule status")
        return 0

    raise ScheduleError(
        f"{system} 上没有内置的定时器支持；请手动把下面的命令加进你的调度器：\n  "
        + " ".join(paths["command"])
    )


def _uid() -> int:
    import os

    return os.getuid()


def uninstall(args: Any, config: dict[str, Any]) -> int:
    if platform.system() == "Darwin":
        target = launchd_path()
        subprocess.run(
            ["launchctl", "bootout", f"gui/{_uid()}/{LAUNCHD_LABEL}"],
            capture_output=True,
            text=True,
        )
        if target.exists():
            target.unlink()
        print(f"✅ 已移除：{target}")
        return 0
    if platform.system() == "Linux":
        subprocess.run(
            ["systemctl", "--user", "disable", "--now", SYSTEMD_TIMER],
            capture_output=True,
            text=True,
        )
        for name in (SYSTEMD_SERVICE, SYSTEMD_TIMER):
            path = systemd_dir() / name
            if path.exists():
                path.unlink()
                print(f"✅ 已移除：{path}")
        return 0
    raise ScheduleError(f"{platform.system()} 上没有可移除的定时器")


def _tail_tick_log(path: Path, lines: int = MAX_LOG_LINES) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    entries = []
    for raw in path.read_text(encoding="utf-8").splitlines()[-lines:]:
        try:
            entries.append(json.loads(raw))
        except ValueError:
            continue
    return entries


def _describe(entry: dict[str, Any]) -> str:
    status = entry.get("status", "?")
    if status == "lock_held":
        return "跳过（已有任务在执行）"
    if status != "ok":
        return f"异常（{status}）"
    return (
        f"due={entry.get('due', 0)} healthy={entry.get('healthy', 0)} "
        f"unchanged={entry.get('unchanged', 0)} errors={entry.get('errors', 0)} "
        f"processed={entry.get('processed', 0)}"
    )


def status(args: Any, config: dict[str, Any]) -> int:
    paths = schedule_paths(args, config)
    entries = _tail_tick_log(paths["tick_log"])

    print(f"配置：{paths['config_path']}")
    print(f"日志：{paths['tick_log']}")
    if platform.system() == "Darwin":
        detail = subprocess.run(
            ["launchctl", "print", f"gui/{_uid()}/{LAUNCHD_LABEL}"],
            capture_output=True,
            text=True,
        )
        if detail.returncode != 0:
            print("定时器：未安装（运行 subscribe schedule install）")
        else:
            state = re_first(r"state = (\S+)", detail.stdout) or "未知"
            exit_code = re_first(r"last exit code = (\S+)", detail.stdout) or "尚未运行"
            runs = re_first(r"\bruns = (\d+)", detail.stdout) or "0"
            print(f"定时器：{state}；累计运行 {runs} 次；上次退出码 {exit_code}")
    elif platform.system() == "Linux":
        detail = subprocess.run(
            ["systemctl", "--user", "is-active", SYSTEMD_TIMER],
            capture_output=True,
            text=True,
        )
        state = detail.stdout.strip() or "未知"
        print(f"定时器：{state}")
    else:
        print("定时器：当前系统没有内置支持")

    if not entries:
        print("最近记录：无（还没有跑过 tick，或日志被清理）")
        return 0
    print(f"最近 {len(entries)} 次：")
    now = datetime.now(timezone.utc)
    for entry in reversed(entries):
        stamp = str(entry.get("ts", "?"))
        age = ""
        try:
            delta = now - datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc
            )
            age = f"（{int(delta.total_seconds() // 60)} 分钟前）"
        except ValueError:
            pass
        print(f"  {stamp}{age} {_describe(entry)}")
    return 0


def re_first(pattern: str, text: str) -> str:
    import re

    match = re.search(pattern, text)
    return match.group(1) if match else ""
