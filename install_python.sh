#!/bin/bash

# Python 安装脚本
# 根据系统类型自动选择安装方法

set -e  # 遇到错误时退出

# 默认值
DEFAULT_PYTHON_VERSION="3.11"
DEFAULT_PYTHON_MIRROR="https://www.python.org/ftp/python"

# 函数：检测系统类型
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
        VERSION=$VERSION_ID
    elif [ -f /etc/lsb-release ]; then
        . /etc/lsb-release
        OS=${DISTRIB_ID,,}
        VERSION=$DISTRIB_RELEASE
    elif [ -f /etc/debian_version ]; then
        OS=debian
        VERSION=$(cat /etc/debian_version)
    elif [ -f /etc/redhat-release ]; then
        if grep -q "CentOS" /etc/redhat-release; then
            OS=centos
        else
            OS=rhel
        fi
        VERSION=$(grep -oE '[0-9]+\.[0-9]+' /etc/redhat-release | head -1)
    else
        OS=unknown
        VERSION=unknown
    fi
    echo "$OS"
}

# 函数：输入 Python 版本
input_python_version() {
    read -p "请输入 python 版本（默认 3.11.9）: " python_version
    if [ -z "$python_version" ]; then
        python_version="3.11.9"
    fi

    # 如果用户只输入了主版本（如 3.11），尝试补全为 .0
    if [[ $python_version =~ ^[0-9]+\.[0-9]+$ ]]; then
        echo "警告：仅输入了主版本号 '$python_version'，将尝试使用 '${python_version}.0'"
        python_version="${python_version}.0"
    fi

    echo "$python_version"
}

# 函数：输入 Python 镜像源
input_python_mirror() {
    read -p "请输入 python 镜像源（默认 $DEFAULT_PYTHON_MIRROR）: " python_mirror
    if [ -z "$python_mirror" ]; then
        python_mirror="$DEFAULT_PYTHON_MIRROR"
    fi
    echo "$python_mirror"
}

# 函数：Debian 系统安装 Python
install_python_debian() {
    local version="$1"
    local mirror="$2"

    echo "在 Debian/Ubuntu 系统上安装 Python $version..."

    # 更新包列表
    sudo apt update

    # 安装编译依赖
    sudo apt install -y build-essential zlib1g-dev libncurses5-dev libgdbm-dev \
        libnss3-dev libssl-dev libreadline-dev libffi-dev libsqlite3-dev wget \
        libbz2-dev libexpat1-dev liblzma-dev tk-dev

    # 下载并编译 Python
    cd /tmp
    wget "$mirror/$version/Python-$version.tgz"
    tar -xf "Python-$version.tgz"
    cd "Python-$version"

    ./configure --enable-optimizations
    make -j$(nproc)
    sudo make altinstall

    echo "Python $version 安装完成！"
}

# 函数：CentOS 系统安装 Python
install_python_centos() {
    local version="$1"
    local mirror="$2"

    echo "在 CentOS/RHEL 系统上安装 Python $version..."

    # 安装 EPEL 仓库（如果需要）
    if ! rpm -q epel-release > /dev/null 2>&1; then
        sudo yum install -y epel-release
    fi

    # 安装编译依赖
    sudo yum groupinstall -y "Development Tools"
    sudo yum install -y gcc openssl-devel bzip2-devel libffi-devel zlib-devel \
        ncurses-devel sqlite-devel readline-devel tk-devel xz-devel

    # 下载并编译 Python
    cd /tmp
    wget "$mirror/$version/Python-$version.tgz"
    tar -xf "Python-$version.tgz"
    cd "Python-$version"

    ./configure --enable-optimizations
    make -j$(nproc)
    sudo make altinstall

    echo "Python $version 安装完成！"
}

# 函数：其他系统安装 Python
install_python_other() {
    local version="$1"
    local mirror="$2"

    echo "在其他系统上安装 Python $version..."
    echo "请手动下载并编译安装：$mirror/$version/Python-$version.tgz"
    echo "或者使用系统的包管理器进行安装。"

    # 尝试通用方法
    cd /tmp
    if command -v wget > /dev/null; then
        wget "$mirror/$version/Python-$version.tgz"
    elif command -v curl > /dev/null; then
        curl -O "$mirror/$version/Python-$version.tgz"
    else
        echo "错误：系统中没有找到 wget 或 curl"
        exit 1
    fi

    tar -xf "Python-$version.tgz"
    cd "Python-$version"

    ./configure --enable-optimizations
    make -j$(nproc)
    sudo make altinstall

    echo "Python $version 安装完成！"
}

# 主函数
main() {
    echo "=== Python 安装脚本 ==="

    # 输入 Python 版本
    python_version=$(input_python_version)

    # 输入 Python 镜像源
    python_mirror=$(input_python_mirror)

    # 检测操作系统
    os_type=$(detect_os)
    echo "检测到操作系统: $os_type"

    # 根据系统类型安装 Python
    case "$os_type" in
        debian|ubuntu|linuxmint|pop|kali|raspbian)
            install_python_debian "$python_version" "$python_mirror"
            ;;
        centos|rhel|fedora|rocky|almalinux)
            install_python_centos "$python_version" "$python_mirror"
            ;;
        *)
            install_python_other "$python_version" "$python_mirror"
            ;;
    esac

    # 验证安装
    if command -v "python$python_version" > /dev/null 2>&1; then
        echo "验证安装："
        "python$python_version" --version
    elif command -v "python${python_version%%.*}" > /dev/null 2>&1; then
        echo "验证安装："
        "python${python_version%%.*}" --version
    else
        echo "注意：可能需要将 /usr/local/bin 添加到 PATH 中"
        echo "或者使用 'python3.$(echo $python_version | cut -d. -f2)' 命令"
    fi
}

# 运行主函数
main "$@"