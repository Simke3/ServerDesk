# ServerDesk

Desktop administration console for Linux servers (PySide6 / Qt). Manages the local machine and any number of
remote servers over SSH from one window.

## Features
- **Dashboard** - CPU, memory, swap, disk gauges, load, uptime, network throughput, history charts, failed services, active alerts
- **Services** - systemd units: filter, start/stop/restart/reload/enable/disable, live `systemctl status`
- **Processes** - sortable list, terminate/kill/pause/resume/renice
- **Logs** - journald (unit, priority, time range) and common log files, search, follow mode, highlighting, export
- **Storage** - filesystems, block devices, inodes, directory usage analyzer
- **Network** - interfaces, routes, DNS, listening ports with owning process, ping/traceroute/DNS, firewall (ufw rules; firewalld/nftables/iptables read-only)
- **Containers** - Docker containers (state, CPU, memory, logs, actions) and images
- **Users & Security** - accounts, groups, active sessions, login history, failed logins, lock/unlock
- **Scheduler** - crontab editor and systemd timers
- **Updates** - apt / dnf / yum / pacman / zypper pending updates, refresh, upgrade all
- **Terminal** - line-based shell on the selected server
- **Servers** - saved SSH profiles (key based, multiplexed connections)
- **Audit log** - every administrative action is recorded (`~/.local/share/serverdesk/audit.log`)
- Threshold alerts with desktop notifications

## Run
    ./run.sh                # creates .venv and starts the app
    ./install.sh            # per-user install with launcher and menu entry

Requires Python 3.10+, PySide6, `openssh-client` for remote servers. Privileged actions use `pkexec` on a local
desktop session (or `sudo -n`), and `sudo -n` on remote servers, so give the SSH user passwordless sudo for the
commands you want to manage from the app.

## Layout
    serverdesk/core/   command execution (local + SSH), metrics, services, logs, ... (no Qt dependency)
    serverdesk/ui/     theme, widgets, context/monitor and one module per page
