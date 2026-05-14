#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Docker 安装脚本
- 检查 Docker 和 Docker Compose 是否已安装
- 如果未安装，则自动安装
- 仅使用 Python 标准库（subprocess, shutil, sys, os）
"""

import os
import shutil
import subprocess
import sys
from typing import Optional


def run_command(cmd: str, check: bool = True, capture_output: bool = False) -> Optional[subprocess.CompletedProcess]:
    """执行 shell 命令"""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            check=check,
            capture_output=capture_output,
            text=True
        )
        return result
    except subprocess.CalledProcessError as e:
        if capture_output:
            print(f"命令执行失败: {cmd}")
            print(f"错误输出: {e.stderr}")
        return None


def is_docker_installed() -> bool:
    """检查 Docker 是否已安装并正常工作"""
    if shutil.which("docker") is None:
        return False

    # 测试 docker 命令是否能正常执行
    result = run_command("docker --version", capture_output=True, check=False)
    return result is not None and result.returncode == 0


def is_docker_compose_installed() -> bool:
    """检查 Docker Compose 是否已安装"""
    # 首先检查新的 docker compose (v2)
    result = run_command("docker compose version", capture_output=True, check=False)
    if result is not None and result.returncode == 0:
        return True

    # 然后检查旧的 docker-compose (v1)
    if shutil.which("docker-compose") is not None:
        result = run_command("docker-compose --version", capture_output=True, check=False)
        return result is not None and result.returncode == 0

    return False


def install_docker() -> bool:
    """安装 Docker"""
    print("正在安装 Docker...")

    # 下载并执行官方安装脚本
    # 使用阿里云镜像加速（国内用户友好）
    install_cmd = 'curl -fsSL https://get.docker.com | sh'

    # 如果在中国大陆，可以使用阿里云镜像
    # install_cmd = 'curl -fsSL https://get.docker.com | sh -s docker --mirror Aliyun'

    result = run_command(install_cmd, check=False)
    if result is None or result.returncode != 0:
        print("❌ Docker 安装失败！")
        return False

    # 启动 Docker 服务
    run_command("sudo systemctl enable docker", check=False)
    run_command("sudo systemctl start docker", check=False)

    print("✅ Docker 安装完成！")
    return True


def install_docker_compose() -> bool:
    """安装 Docker Compose v2 (作为 Docker CLI 插件)"""
    print("正在安装 Docker Compose...")

    # 创建 CLI 插件目录
    plugin_dir = os.path.expanduser("~/.docker/cli-plugins")
    os.makedirs(plugin_dir, exist_ok=True)

    # 获取系统架构
    arch_result = run_command("uname -m", capture_output=True, check=False)
    if arch_result is None:
        print("无法确定系统架构，使用默认 x86_64")
        arch = "x86_64"
    else:
        arch_map = {
            "x86_64": "x86_64",
            "aarch64": "aarch64",
            "arm64": "aarch64",
            "armv7l": "armv7"
        }
        arch = arch_map.get(arch_result.stdout.strip(), "x86_64")

    # 下载 Docker Compose v2
    download_url = f"https://github.com/docker/compose/releases/latest/download/docker-compose-linux-{arch}"
    install_path = os.path.join(plugin_dir, "docker-compose")

    download_cmd = f"curl -SL {download_url} -o {install_path}"
    result = run_command(download_cmd, check=False)

    if result is None or result.returncode != 0:
        print("❌ Docker Compose 下载失败！")
        return False

    # 添加执行权限
    run_command(f"chmod +x {install_path}", check=False)

    print("✅ Docker Compose 安装完成！")
    return True


def add_user_to_docker_group() -> None:
    """将当前用户添加到 docker 组，避免每次使用 sudo"""
    username = os.environ.get('USER', '')
    if not username:
        return

    print(f"正在将用户 '{username}' 添加到 docker 组...")
    run_command(f"sudo usermod -aG docker {username}", check=False)
    print("💡 请重新登录或运行 'newgrp docker' 以应用组更改")


def main():
    """主函数"""
    print("=== Docker 安装脚本 ===")

    # 检查 Docker
    if is_docker_installed():
        print("✅ Docker 已安装")
    else:
        print("❌ Docker 未安装，开始安装...")
        if not install_docker():
            print("Docker 安装失败，退出")
            sys.exit(1)

    # 检查 Docker Compose
    if is_docker_compose_installed():
        print("✅ Docker Compose 已安装")
    else:
        print("❌ Docker Compose 未安装，开始安装...")
        if not install_docker_compose():
            print("Docker Compose 安装失败")
        else:
            print("✅ Docker Compose 安装成功")

    # 添加用户到 docker 组
    add_user_to_docker_group()

    # 验证安装
    print("\n=== 验证安装结果 ===")
    docker_result = run_command("docker --version", capture_output=True, check=False)
    if docker_result:
        print(f"Docker 版本: {docker_result.stdout.strip()}")

    compose_result = run_command("docker compose version", capture_output=True, check=False)
    if compose_result and compose_result.returncode == 0:
        print(f"Docker Compose 版本: {compose_result.stdout.strip()}")
    else:
        # 尝试旧版本
        old_compose = run_command("docker-compose --version", capture_output=True, check=False)
        if old_compose:
            print(f"Docker Compose 版本: {old_compose.stdout.strip()}")

    print("\n🎉 安装完成！")
    print("💡 提示：如果刚添加了 docker 组，请重新登录或运行 'newgrp docker'")


if __name__ == "__main__":
    # 检查是否为 root 或有 sudo 权限
    if os.geteuid() == 0:
        print("警告: 不建议以 root 用户运行此脚本")
        print("建议以普通用户运行，脚本会自动使用 sudo")

    main()
