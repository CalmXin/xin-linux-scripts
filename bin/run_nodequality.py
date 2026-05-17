#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NodeQuality 的 Python 实现
在临时 chroot 环境中运行服务器性能测试
"""

import argparse
import atexit
import json
import os
import platform
import shutil
import signal
import subprocess
import sys
import textwrap
import time
import urllib.request
from pathlib import Path
from typing import Dict, Optional, Tuple, Any

# 全局变量
WORK_DIR: Optional[Path] = None
BENCH_OS_URL = "https://github.com/LloydAsp/NodeQuality/releases/download/v0.0.2/BenchOs.tar.gz"
BENCH_OS_ARM_URL = "https://github.com/LloydAsp/NodeQuality/releases/download/v0.0.2/BenchOs-arm.tar.gz"
RAW_FILE_PREFIX = "https://raw.githubusercontent.com/LloydAsp/NodeQuality/refs/heads/main"

# 语言字符串
LANG_STRINGS: Dict[str, Dict[str, str]] = {
    "en": {
        "err01": "Error: work_dir does not contain 'nodequality'!",
        "err02": "Error: Unsupported parameters!",
        "err03": "Error: the specified work_dir does not exist or is not readable/writable!",
        "cleanup": "Cleaning, please wait a moment.",
        "clean_fail": "An unexpected situation occurred: the BenchOS directory mount was not cleaned up properly. For safety, please reboot and then delete this directory.",
        "ask_hq": "Run HardwareQuality test? (Enter for default 'y', 'f' for fast mode, 'v' for all test details) [y/f/v/n]: ",
        "ask_iq": "Run IPQuality test? (Enter for default 'y') [y/n]: ",
        "ask_nq": "Run NetQuality test? (Enter for default 'y', 'l' for low-data mode) [y/l/n]: ",
        "ask_bt": "Run Backroute Trace test? (Enter for default 'y') [y/n]: ",
        "cleanup_before": "Clean Up before Installation",
        "loadbench": "Load BenchOs",
        "basicinfo": "Hardware Info",
        "run_hq": "Running Hardware Quality Test...",
        "run_iq": "Running IP Quality Test...",
        "run_nq": "Running Network Quality Test...",
        "run_bt": "Running Backroute Trace...",
        "cleanup_after": "Clean Up after Installation"
    },
    "cn": {
        "err01": "错误：work_dir不包含'nodequality'！",
        "err02": "错误：不支持的参数！",
        "err03": "错误：指定的 work_dir 不存在，或不可读/不可写！",
        "cleanup": "清理中，请稍后。",
        "clean_fail": "出现了预料之外的情况，BenchOS目录的挂载未被清理干净，保险起见请重启后删除该目录。",
        "ask_hq": "运行 HardwareQuality 测试？（回车默认 'y'，'f' 为快速模式，'v' 为深度模式）[y/f/v/n]：",
        "ask_iq": "运行 IPQuality 测试？（回车默认 'y'）[y/n]：",
        "ask_nq": "运行 NetQuality 测试？（回车默认 'y'，'l' 为低流量模式）[y/l/n]：",
        "ask_bt": "运行 回程路由追踪（Backroute Trace）测试？（回车默认 'y'）[y/n]：",
        "cleanup_before": "安装前清理",
        "loadbench": "加载 BenchOs",
        "basicinfo": "硬件信息",
        "run_hq": "正在运行硬件质量测试...",
        "run_iq": "正在运行 IP 质量测试...",
        "run_nq": "正在运行网络质量测试...",
        "run_bt": "正在运行回程路由追踪...",
        "cleanup_after": "安装后清理"
    }
}

# 颜色代码
COLORS = {
    "red": "\033[0;31m",
    "yellow": "\033[0;33m",
    "blue": "\033[0;36m",
    "green": "\033[0;32m",
    "red_bold": "\033[1;31m",
    "yellow_bold": "\033[1;33m",
    "blue_bold": "\033[1;36m",
    "green_bold": "\033[1;32m",
    "cyan_bold": "\033[1;36m",
    "reset": "\033[0m"
}


class NodeQuality:
    """NodeQuality 主类"""

    def __init__(self):
        self.lang = "cn"
        self.opt_ipv = ""
        self.opt_lang = ""
        self.run_hardware_quality_test = "y"
        self.run_ip_quality_test = "y"
        self.run_net_quality_test = "y"
        self.run_net_trace_test = "y"
        self.work_dir: Optional[Path] = None
        self.bench_os_url = BENCH_OS_URL

        # 检测 ARM 架构
        if any(arch in platform.machine().lower() for arch in ['arm', 'aarch64']):
            self.bench_os_url = BENCH_OS_ARM_URL

    @staticmethod
    def color_print(text: str, color: str) -> None:
        """打印带颜色的文本"""
        print(f"{COLORS[color]}{text}{COLORS['reset']}")

    def get_lang_string(self, key: str) -> str:
        """获取语言字符串"""
        lang_key = f"{self.lang}.{key}"
        fallback_key = f"en.{key}"
        return LANG_STRINGS.get(self.lang, {}).get(key, LANG_STRINGS["en"].get(key, ""))

    def parse_args(self) -> None:
        """解析命令行参数"""
        parser = argparse.ArgumentParser(add_help=False)

        # 自定义参数处理
        args = sys.argv[1:]
        i = 0
        custom_work_dir = None

        while i < len(args):
            arg = args[i]
            if arg in ['-4']:
                if self.opt_ipv != "-6":
                    self.opt_ipv = "-4"
            elif arg in ['-6']:
                if self.opt_ipv != "-4":
                    self.opt_ipv = "-6"
            elif arg in ['-D', '-d'] and i + 1 < len(args):
                custom_work_dir = Path(args[i + 1]).resolve()
                if not custom_work_dir.exists() or not os.access(custom_work_dir, os.R_OK | os.W_OK):
                    self.color_print(self.get_lang_string("err03"), "red")
                    sys.exit(1)
                i += 1
            elif arg in ['-E', '-e']:
                self.lang = "en"
                self.opt_lang = "-E"
            elif arg.startswith('-'):
                self.color_print(self.get_lang_string("err02"), "red")
            i += 1

        # 设置工作目录
        current_time = time.strftime("%Y_%m_%d_%H_%M_%S")
        base_work_dir = f".nodequality{current_time}"

        if custom_work_dir:
            self.work_dir = custom_work_dir / base_work_dir
        else:
            self.work_dir = Path.cwd() / base_work_dir

        global WORK_DIR
        WORK_DIR = self.work_dir

    def start_ascii(self) -> None:
        """打印 ASCII 艺术字和介绍"""
        ascii_art = """
            ███╗   ██╗ ██████╗ ██████╗ ███████╗ ██████╗ ██╗   ██╗ █████╗ ██╗     ██╗████████╗██╗   ██╗
            ████╗  ██║██╔═══██╗██╔══██╗██╔════╝██╔═══██╗██║   ██║██╔══██╗██║     ██║╚══██╔══╝╚██╗ ██╔╝
            ██╔██╗ ██║██║   ██║██║  ██║█████╗  ██║   ██║██║   ██║███████║██║     ██║   ██║    ╚████╔╝ 
            ██║╚██╗██║██║   ██║██║  ██║██╔══╝  ██║▄▄ ██║██║   ██║██╔══██║██║     ██║   ██║     ╚██╔╝  
            ██║ ╚████║╚██████╔╝██████╔╝███████╗╚██████╔╝╚██████╔╝██║  ██║███████╗██║   ██║      ██║   
            ╚═╝  ╚═══╝ ╚═════╝ ╚═════╝ ╚══════╝ ╚══▀▀═╝  ╚═════╝ ╚═╝  ╚═╝╚══════╝╚═╝   ╚═╝      ╚═╝   
            """
        self.color_print(textwrap.dedent(ascii_art), "cyan_bold")

        if self.lang == "en":
            intro = """
            Benchmark script for server, collects basic hardware information, IP quality and network quality

            The benchmark will be performed in a temporary system, and all traces will be deleted after that.
            Therefore, it has no impact on the original environment and supports almost all linux systems.
            
            Author: Lloyd@nodeseek.com
            Github: github.com/LloydAsp/NodeQuality
            Command: bash <(curl -sL https://run.NodeQuality.com)
            """
        else:
            intro = """
                网络服务器的专业测评脚本，检测硬件质量、IP质量和网络质量
    
                脚本测试是纯净的，在临时系统中执行，之后所有的痕迹都会被删除
                因此，它不会对原始环境产生任何影响，并且支持几乎所有 Linux 系统
                
                作者：Lloyd@nodeseek.com
                仓库：github.com/LloydAsp/NodeQuality
                命令：bash <(curl -sL https://run.NodeQuality.com)
                """

        print(textwrap.dedent(intro))
        print()

    def pre_init(self) -> None:
        """初始化工作目录"""
        self.work_dir.mkdir(parents=True, exist_ok=True)
        os.chdir(self.work_dir)
        self.work_dir = Path.cwd()

    def pre_cleanup(self) -> None:
        """预清理"""
        self.clear_mount()
        if "nodequality" not in str(self.work_dir):
            self.color_print(self.get_lang_string("err01"), "red")
            sys.exit(1)
        # 清空目录内容
        for item in self.work_dir.iterdir():
            if item.is_file() or item.is_symlink():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)

    def clear_mount(self) -> None:
        """清理挂载点"""
        bench_os_dir = self.work_dir / "BenchOs"
        swap_file = self.work_dir / "swap"

        # 关闭 swap
        try:
            subprocess.run(["swapoff", str(swap_file)], check=False, capture_output=True)
        except Exception:
            pass

        # 卸载挂载点
        mount_points = [
            bench_os_dir / "proc",
            bench_os_dir / "sys",
            bench_os_dir / "dev"
        ]

        for mount_point in mount_points:
            if mount_point.exists():
                try:
                    if mount_point.name == "dev":
                        subprocess.run(["umount", "-R", str(mount_point)], check=False, capture_output=True)
                    else:
                        subprocess.run(["umount", str(mount_point)], check=False, capture_output=True)
                except Exception:
                    pass

    def load_bench_os(self) -> None:
        """加载 BenchOS"""
        os.chdir(self.work_dir)

        # 删除旧的 BenchOs 目录
        bench_os_dir = self.work_dir / "BenchOs"
        if bench_os_dir.exists():
            shutil.rmtree(bench_os_dir)

        # 下载 BenchOs
        bench_os_tar = self.work_dir / "BenchOs.tar.gz"
        self.color_print(f"Downloading {self.bench_os_url}...", "blue")
        urllib.request.urlretrieve(self.bench_os_url, bench_os_tar)

        # 解压
        subprocess.run(["tar", "-xzf", "BenchOs.tar.gz"], check=True)
        os.chdir(bench_os_dir)

        # 挂载必要的文件系统
        subprocess.run(["mount", "-t", "proc", "/proc", "proc/"], check=True)
        subprocess.run(["mount", "--bind", "/sys", "sys/"], check=True)
        subprocess.run(["mount", "--rbind", "/dev", "dev/"], check=True)
        subprocess.run(["mount", "--make-rslave", "dev"], check=True)

        # 复制 resolv.conf
        resolv_conf = bench_os_dir / "etc" / "resolv.conf"
        if resolv_conf.exists():
            resolv_conf.unlink()
        shutil.copy("/etc/resolv.conf", resolv_conf)

    def chroot_run(self, command: str) -> subprocess.CompletedProcess:
        """在 chroot 环境中运行命令"""
        bench_os_dir = self.work_dir / "BenchOs"
        full_command = f"chroot {bench_os_dir} /bin/bash -c '{command}'"
        return subprocess.run(full_command, shell=True, capture_output=True, text=True)

    def load_part(self) -> None:
        """加载 swap 部分脚本"""
        # 这里需要实现 swap.sh 的功能
        # 由于无法直接执行远程 shell 脚本，我们需要在 Python 中实现相同逻辑
        pass

    def load_3rd_program(self) -> None:
        """加载第三方程序"""
        cmd = "wget https://github.com/nxtrace/NTrace-core/releases/download/v1.3.7/nexttrace_linux_amd64 -qO /usr/local/bin/nexttrace && chmod u+x /usr/local/bin/nexttrace"
        self.chroot_run(cmd)

    def run_header(self) -> str:
        """运行 header 脚本"""
        cmd = f"bash <(curl -Ls {RAW_FILE_PREFIX}/part/header.sh)"
        result = self.chroot_run(cmd)
        return result.stdout

    def detect_virt(self) -> str:
        """检测虚拟化类型"""
        if Path("/run/systemd/container").exists():
            return Path("/run/systemd/container").read_text().strip()
        if Path("/.dockerenv").exists():
            return "docker"
        if Path("/run/.containerenv").exists():
            return "podman"
        if Path("/proc/1/cgroup").exists():
            cgroup_content = Path("/proc/1/cgroup").read_text()
            if "lxc" in cgroup_content:
                return "lxc"
        if Path("/proc/cpuinfo").exists():
            cpuinfo_content = Path("/proc/cpuinfo").read_text()
            if "hypervisor" in cpuinfo_content:
                return "kvm"
        return "none"

    def detect_testdev_type(self, dev: str) -> str:
        """检测设备类型"""
        try:
            real_dev = Path(dev).resolve()
            dev_name = real_dev.name

            if dev_name.startswith("md"):
                # RAID 设备
                if Path("/proc/mdstat").exists():
                    mdstat = Path("/proc/mdstat").read_text()
                    for line in mdstat.split('\n'):
                        if line.startswith(dev_name):
                            if "raid" in line:
                                import re
                                match = re.search(r'raid\d+', line)
                                if match:
                                    return match.group(0).upper()
                            return "RAID"
                return "RAID"

            if dev_name.startswith("dm-") or "mapper" in str(real_dev):
                return "LVM"

            # 检查是否为磁盘或分区
            try:
                result = subprocess.run(["lsblk", "-no", "TYPE", dev],
                                        capture_output=True, text=True, check=True)
                if "disk" in result.stdout or "part" in result.stdout:
                    return "DISK"
            except subprocess.CalledProcessError:
                pass

        except Exception:
            pass

        return ""

    def get_md_mount(self, md: str) -> str:
        """获取 MD 设备的挂载点"""
        try:
            # 尝试使用 findmnt
            result = subprocess.run(["findmnt", "-n", "-o", "TARGET", f"/dev/{md}"],
                                    capture_output=True, text=True, check=False)
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()

            # 尝试使用 lsblk
            result = subprocess.run(["lsblk", "-o", "NAME,PKNAME,TYPE,MOUNTPOINT", "-r"],
                                    capture_output=True, text=True, check=False)
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                mounts = []
                for line in lines[1:]:  # 跳过标题行
                    parts = line.split()
                    if len(parts) >= 4 and parts[1] == md and parts[3]:
                        mounts.append(parts[3])
                if mounts:
                    return ",".join(sorted(set(mounts)))

        except Exception:
            pass

        return ""

    def pre_fetch_info(self) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
        """预获取系统信息"""
        virt_type = self.detect_virt()

        # 获取操作系统信息
        osinfo: Dict[str, Any] = {}
        try:
            result = subprocess.run(["ps", "-e"], capture_output=True, text=True, check=False)
            osinfo["proc"] = len(result.stdout.strip().split('\n')) - 1 if result.stdout else 0
        except Exception:
            osinfo["proc"] = 0

        # 获取用户数量
        try:
            if shutil.which("loginctl"):
                result = subprocess.run(["loginctl", "list-users"], capture_output=True, text=True, check=False)
                if result.returncode == 0:
                    user_count = len(result.stdout.strip().split('\n')) - 1
                    if user_count > 0:
                        osinfo["user"] = user_count
            elif platform.system() == "Darwin":
                result = subprocess.run(["stat", "-f", "%Su", "/dev/console"], capture_output=True, text=True,
                                        check=False)
                if result.returncode == 0:
                    osinfo["user"] = 1
            else:
                result = subprocess.run(["who"], capture_output=True, text=True, check=False)
                if result.returncode == 0:
                    user_count = len(result.stdout.strip().split('\n'))
                    if user_count > 0:
                        osinfo["user"] = user_count
        except Exception:
            pass

        # 获取服务信息
        if virt_type in ["docker", "podman", "lxc", "container"]:
            # 容器环境中可能没有 systemd
            osinfo["svcr"] = ""
            osinfo["svct"] = ""
        elif shutil.which("systemctl"):
            try:
                result = subprocess.run(["systemctl", "list-units", "--type=service", "--state=running"],
                                        capture_output=True, text=True, check=False)
                if result.returncode == 0:
                    running_services = len([line for line in result.stdout.split('\n') if '.service' in line])
                    osinfo["svcr"] = running_services

                result = subprocess.run(["systemctl", "list-unit-files", "--type=service"],
                                        capture_output=True, text=True, check=False)
                if result.returncode == 0:
                    total_services = len([line for line in result.stdout.split('\n') if '.service' in line])
                    osinfo["svct"] = total_services
            except Exception:
                pass
        elif shutil.which("rc-service"):
            try:
                result = subprocess.run(["rc-service", "-r"], capture_output=True, text=True, check=False)
                if result.returncode == 0:
                    osinfo["svcr"] = len(result.stdout.strip().split('\n'))

                result = subprocess.run(["rc-service", "-l"], capture_output=True, text=True, check=False)
                if result.returncode == 0:
                    osinfo["svct"] = len(result.stdout.strip().split('\n'))
            except Exception:
                pass
        elif platform.system() == "Darwin" and shutil.which("launchctl"):
            try:
                result = subprocess.run(["launchctl", "list"], capture_output=True, text=True, check=False)
                if result.returncode == 0:
                    service_count = len(result.stdout.strip().split('\n')) - 1
                    osinfo["svcr"] = service_count
                    osinfo["svct"] = service_count
            except Exception:
                pass

        # 获取内存信息
        meminfo: Dict[str, Any] = {}
        if virt_type == "kvm":
            try:
                if shutil.which("lsmod"):
                    result = subprocess.run(["lsmod"], capture_output=True, text=True, check=False)
                    if result.returncode == 0 and "virtio_balloon" in result.stdout:
                        meminfo["balloon"] = 1
                    else:
                        meminfo["balloon"] = 0

                ksm_path = Path("/sys/kernel/mm/ksm/run")
                if ksm_path.exists() and ksm_path.read_text().strip() == "1":
                    meminfo["ksm"] = 1
                else:
                    meminfo["ksm"] = 0
            except Exception:
                meminfo["balloon"] = 0
                meminfo["ksm"] = 0
        elif virt_type == "lxc":
            try:
                block_devices = Path("/sys/devices/virtual/block")
                if block_devices.exists():
                    dm_count = len([d for d in block_devices.iterdir() if d.name.startswith("dm")])
                    meminfo["neighbor"] = dm_count
            except Exception:
                meminfo["neighbor"] = 0

        # 获取磁盘信息
        diskinfo: Dict[str, Any] = {}
        ridx = 0

        if Path("/proc/mdstat").exists():
            mdstat_content = Path("/proc/mdstat").read_text()
            for line in mdstat_content.split('\n'):
                import re
                match = re.match(r'^(md\d+)\s*:\s*active\s+([a-z0-9]+)\s+(.*)$', line)
                if match:
                    ridx += 1
                    rname = match.group(1)
                    rlevel = match.group(2).upper()
                    rdevs_raw = match.group(3)

                    # 提取设备列表
                    rdevs_parts = []
                    for part in rdevs_raw.split():
                        if '[' in part and ']' in part:
                            rdevs_parts.append(part)

                    rdevs = " ".join(rdevs_parts)

                    diskinfo[f"raid{ridx}.name"] = rname
                    diskinfo[f"raid{ridx}.level"] = rlevel
                    diskinfo[f"raid{ridx}.devs"] = rdevs
                    diskinfo[f"raid{ridx}.mount"] = self.get_md_mount(rname)

        diskinfo["raid_count"] = ridx
        diskinfo["testdir"] = str(self.work_dir.parent)

        # 获取测试设备
        try:
            result = subprocess.run(["df", "--output=source", str(self.work_dir)],
                                    capture_output=True, text=True, check=True)
            testdev = result.stdout.strip().split('\n')[1] if len(result.stdout.strip().split('\n')) > 1 else ""
            diskinfo["testdev"] = testdev.lstrip("/dev/")
            diskinfo["testdev_type"] = self.detect_testdev_type(testdev)

            if diskinfo["testdev_type"].startswith("RAID"):
                # 这里需要实现从 diskinfo 中获取成员设备的逻辑
                diskinfo["testdev_members"] = ""
                diskinfo["testdev_mount"] = ""
        except Exception:
            diskinfo["testdev"] = ""
            diskinfo["testdev_type"] = ""

        return osinfo, meminfo, diskinfo

    def run_HardwareQuality(self) -> str:
        """运行硬件质量测试"""
        params = ""
        if self.run_hardware_quality_test.lower() == "f":
            params = " -F"
        elif self.run_hardware_quality_test.lower() == "v":
            params = " -V"

        # 获取系统信息
        osinfo, meminfo, diskinfo = self.pre_fetch_info()

        # 准备环境变量
        nqenv = f"osinfo={json.dumps(osinfo)} meminfo={json.dumps(meminfo)} diskinfo={json.dumps(diskinfo)}"

        # 构建命令
        cmd_parts = ["env", f"NQENV={nqenv}", "bash", "-s", "--"]
        if self.opt_lang:
            cmd_parts.append(self.opt_lang)
        if params:
            cmd_parts.append(params)
        cmd_parts.extend(["-y", "-o", "/result/hardware_quality.json"])

        cmd = f"curl -Ls https://Hardware.Check.Place | {' '.join(cmd_parts)}"
        result = self.chroot_run(cmd)
        return result.stdout

    def run_ip_quality(self) -> str:
        """运行 IP 质量测试"""
        cmd_parts = ["bash", "<(curl -Ls https://IP.Check.Place)"]
        if self.opt_ipv:
            cmd_parts.append(self.opt_ipv)
        if self.opt_lang:
            cmd_parts.append(self.opt_lang)
        cmd_parts.extend(["-y", "-o", "/result/ip_quality.json"])

        cmd = " ".join(cmd_parts)
        result = self.chroot_run(cmd)
        return result.stdout

    def run_net_quality(self) -> str:
        """运行网络质量测试"""
        params = ""
        if self.run_net_quality_test.lower() == "l":
            params = " -L"

        cmd_parts = ["bash", "<(curl -Ls https://Net.Check.Place)"]
        if self.opt_ipv:
            cmd_parts.append(self.opt_ipv)
        if self.opt_lang:
            cmd_parts.append(self.opt_lang)
        if params:
            cmd_parts.append(params)
        cmd_parts.extend(["-y", "-o", "/result/net_quality.json"])

        cmd = " ".join(cmd_parts)
        result = self.chroot_run(cmd)
        return result.stdout

    def run_net_trace(self) -> str:
        """运行网络追踪测试"""
        cmd_parts = ["bash", "<(curl -Ls https://Net.Check.Place)"]
        if self.opt_ipv:
            cmd_parts.append(self.opt_ipv)
        if self.opt_lang:
            cmd_parts.append(self.opt_lang)
        cmd_parts.extend(["-R", "-n", "-S", "123", "-o", "/result/backroute_trace.json"])

        cmd = " ".join(cmd_parts)
        result = self.chroot_run(cmd)
        return result.stdout

    def upload_result(self) -> None:
        """上传结果"""
        # 在 chroot 环境中创建 zip 文件
        zip_cmd = "zip -j - '/result/*'"
        result = self.chroot_run(zip_cmd)

        # 将 zip 内容写入文件
        zip_file = self.work_dir / "result.zip"
        with open(zip_file, 'wb') as f:
            f.write(result.stdout.encode('latin1'))  # zip 输出是二进制

        # 上传到 API
        upload_api = "https://api.nodequality.com/api/v1/record"
        try:
            with open(zip_file, 'rb') as f:
                import base64
                zip_data = base64.b64encode(f.read()).decode('utf-8')
                req = urllib.request.Request(upload_api, data=zip_data.encode('utf-8'))
                req.add_header('Content-Type', 'application/octet-stream')
                urllib.request.urlopen(req)
        except Exception as e:
            print(f"Upload failed: {e}")

    def post_cleanup(self) -> None:
        """清理后处理"""
        try:
            # 卸载 dev
            bench_os_dir = self.work_dir / "BenchOs"
            subprocess.run(["chroot", str(bench_os_dir), "umount", "-R", "/dev"],
                           check=False, capture_output=True)

            # 清理挂载
            self.clear_mount()

            # 检查是否还有挂载
            self.post_check_mount()

            # 删除 BenchOs 目录
            if (self.work_dir / "BenchOs").exists():
                shutil.rmtree(self.work_dir / "BenchOs")

            # 删除整个工作目录
            if "nodequality" in str(self.work_dir):
                shutil.rmtree(self.work_dir)
            else:
                self.color_print(self.get_lang_string("err01"), "red")
                sys.exit(1)

        except Exception as e:
            print(f"Cleanup error: {e}")

        sys.exit(0)

    def sig_cleanup(self, signum, frame) -> None:
        """信号处理清理函数"""
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        signal.signal(signal.SIGHUP, signal.SIG_IGN)

        self.color_print(self.get_lang_string("cleanup"), "green_bold")
        self.post_cleanup()

    def post_check_mount(self) -> None:
        """检查挂载是否清理干净"""
        try:
            result = subprocess.run(["mount"], capture_output=True, text=True, check=False)
            if "nodequality" in result.stdout:
                error_msg = self.get_lang_string("clean_fail")
                error_log = self.work_dir / "error.log"
                with open(error_log, 'w') as f:
                    f.write(error_msg)
                self.color_print(error_msg, "red")
                sys.exit(1)
        except Exception:
            pass

    def ask_question(self) -> None:
        """询问用户要运行哪些测试"""
        # 硬件质量测试
        print(f"{COLORS['yellow_bold']}{self.get_lang_string('ask_hq')}{COLORS['reset']}", end="")
        self.run_hardware_quality_test = input().strip() or "y"

        # IP 质量测试
        print(f"{COLORS['yellow_bold']}{self.get_lang_string('ask_iq')}{COLORS['reset']}", end="")
        self.run_ip_quality_test = input().strip() or "y"

        # 网络质量测试
        print(f"{COLORS['yellow_bold']}{self.get_lang_string('ask_nq')}{COLORS['reset']}", end="")
        self.run_net_quality_test = input().strip() or "y"

        # 回程路由追踪
        print(f"{COLORS['yellow_bold']}{self.get_lang_string('ask_bt')}{COLORS['reset']}", end="")
        self.run_net_trace_test = input().strip() or "y"

    def main(self) -> None:
        """主函数"""
        # 设置信号处理器
        signal.signal(signal.SIGINT, self.sig_cleanup)
        signal.signal(signal.SIGTERM, self.sig_cleanup)
        signal.signal(signal.SIGHUP, self.sig_cleanup)

        # 注册退出清理函数
        atexit.register(self.post_cleanup)

        # 开始
        self.start_ascii()
        self.ask_question()

        self.color_print(self.get_lang_string("cleanup_before"), "green_bold")
        self.pre_init()
        self.pre_cleanup()

        self.color_print(self.get_lang_string("loadbench"), "green_bold")
        self.load_bench_os()

        self.load_part()
        self.load_3rd_program()

        self.color_print(self.get_lang_string("basicinfo"), "green_bold")

        result_directory = self.work_dir / "BenchOs" / "result"
        result_directory.mkdir(parents=True, exist_ok=True)

        # 运行 header
        header_info = self.run_header()
        with open(result_directory / "header_info.log", 'w') as f:
            f.write(header_info)

        # 运行各项测试
        if self.run_hardware_quality_test.lower() in ['y', 'f', 'v']:
            self.color_print(self.get_lang_string("run_hq"), "green_bold")
            hq_result = self.run_HardwareQuality()
            with open(result_directory / "hardware_quality.log", 'w') as f:
                f.write(hq_result)

        if self.run_ip_quality_test.lower() == 'y':
            self.color_print(self.get_lang_string("run_iq"), "green_bold")
            iq_result = self.run_ip_quality()
            with open(result_directory / "ip_quality.log", 'w') as f:
                f.write(iq_result)

        if self.run_net_quality_test.lower() in ['y', 'l']:
            self.color_print(self.get_lang_string("run_nq"), "green_bold")
            nq_result = self.run_net_quality()
            with open(result_directory / "net_quality.log", 'w') as f:
                f.write(nq_result)

        if self.run_net_trace_test.lower() == 'y':
            self.color_print(self.get_lang_string("run_bt"), "green_bold")
            bt_result = self.run_net_trace()
            with open(result_directory / "backroute_trace.log", 'w') as f:
                f.write(bt_result)

        # 上传结果
        self.upload_result()

        self.color_print(self.get_lang_string("cleanup_after"), "green_bold")
        self.post_cleanup()


def main():
    """入口点"""
    try:
        app = NodeQuality()
        app.parse_args()
        app.main()
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
