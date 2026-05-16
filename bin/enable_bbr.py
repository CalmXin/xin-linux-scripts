import subprocess
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
    # sysctl 输出形如: net.ipv4.tcp_congestion_control = bbr
    parts = output.split('=', 1)
    if len(parts) < 2:
        return False
    current_algo = parts[1].strip().lower()
    return current_algo == 'bbr'


def enable_bbr() -> None:
    """开启 BBR"""
    if is_bbr_enabled():
        print("BBR 已开启。")
        return

    if not is_support_bbr():
        print("当前系统不支持 BBR（内核版本过低或未编译 BBR 模块）。")
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
    if is_bbr_enabled():
        print("BBR 已成功开启。")
    else:
        print("BBR 启用失败：验证未通过。")


if __name__ == '__main__':
    enable_bbr()
