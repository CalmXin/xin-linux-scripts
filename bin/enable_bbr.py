import re
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import List, Optional


def _run_command(cmd: List[str]) -> Optional[str]:
    """执行 shell 命令并返回标准输出（strip 后），失败则返回 None"""
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=True,
            text=True,
            timeout=10
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return None


def is_support_bbr() -> bool:
    """检测当前系统是否支持 BBR（通过检查可用的拥塞控制算法）"""
    output = _run_command(['sysctl', 'net.ipv4.tcp_available_congestion_control'])
    if output is None:
        return False
    return 'bbr' in output.lower().split()


def is_bbr_enabled() -> bool:
    """检测当前是否已启用 BBR"""
    output = _run_command(['sysctl', 'net.ipv4.tcp_congestion_control'])
    if output is None:
        return False
    parts = output.split('=', 1)
    if len(parts) < 2:
        return False
    current_algo = parts[1].strip().lower()
    return current_algo == 'bbr'


def get_kernel_version() -> Optional[tuple]:
    """获取内核版本，返回 (major, minor, patch) 元组，如 (5, 4, 0)"""
    output = _run_command(['uname', '-r'])
    if not output:
        return None
    # 匹配形如 5.4.0-100-generic 的版本号
    match = re.match(r'(\d+)\.(\d+)(?:\.(\d+))?', output)
    if not match:
        return None
    major = int(match.group(1))
    minor = int(match.group(2))
    patch = int(match.group(3)) if match.group(3) else 0
    return major, minor, patch


def try_load_bbr_module() -> bool:
    """尝试加载 tcp_bbr 内核模块"""
    try:
        subprocess.run(
            ['modprobe', 'tcp_bbr'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
            timeout=5
        )
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return False


def persist_bbr_config() -> None:
    """将 BBR 配置写入 /etc/sysctl.d/99-bbr.conf 以实现持久化"""
    config_content = """
    # Enabled by BBR setup script
    net.core.default_qdisc=fq
    net.ipv4.tcp_congestion_control=bbr
    """
    config_content = textwrap.dedent(config_content).strip()
    config_path = "/etc/sysctl.d/99-bbr.conf"

    # 检查是否已存在相同配置（避免重复）
    if Path(config_path).exists():
        try:
            with open(config_path, 'r') as f:
                existing = f.read()
            if 'tcp_congestion_control=bbr' in existing and 'default_qdisc=fq' in existing:
                print("BBR 配置已持久化，无需重复写入。")
                return
        except (OSError, IOError):
            pass  # 忽略读取错误，继续覆盖写入

    # 写入配置文件
    try:
        with open(config_path, 'w') as f:
            f.write(config_content)
        print(f"✅ BBR 配置已持久化到 {config_path}")
    except (OSError, IOError) as e:
        print(f"⚠️ 无法写入持久化配置（请确保以 root 权限运行）: {e}")
        sys.exit(1)


def enable_bbr() -> None:
    """开启 BBR，若未支持但内核 >= 4.9，则尝试加载模块"""
    if is_bbr_enabled():
        print("BBR 已开启。")
        return

    if is_support_bbr():
        # 支持但未启用，直接启用
        pass
    else:
        # 不支持，检查内核版本
        kernel = get_kernel_version()
        if kernel is None:
            print("无法获取内核版本，跳过 BBR 安装。")
            return

        major, minor, _ = kernel
        if major > 4 or (major == 4 and minor >= 9):
            print(f"检测到内核版本 {kernel}，尝试加载 BBR 模块...")
            if try_load_bbr_module():
                print("BBR 模块加载成功。")
                # 重新检查是否支持
                if not is_support_bbr():
                    print("警告：模块加载成功，但 sysctl 仍未显示 bbr 可用。")
                    return
            else:
                print("加载 BBR 模块失败（可能权限不足或模块不存在）。")
                return
        else:
            print(f"内核版本 {kernel} 过低，BBR 需要 Linux 4.9+。")
            return

    # 设置队列规则为 fq（BBR 推荐）
    try:
        subprocess.run(
            ['sysctl', '-w', 'net.core.default_qdisc=fq'],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        print("设置 net.core.default_qdisc=fq 失败，请检查权限（可能需要 root）。")
        return

    # 启用 BBR
    try:
        subprocess.run(
            ['sysctl', '-w', 'net.ipv4.tcp_congestion_control=bbr'],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        print("启用 BBR 失败，请检查权限（可能需要 root）。")
        return

    # 验证是否成功启用
    if not is_bbr_enabled():
        print("BBR 启用失败：验证未通过。")
        sys.exit(0)

    print("BBR 已成功开启。")
    persist_bbr_config()


if __name__ == '__main__':
    enable_bbr()
