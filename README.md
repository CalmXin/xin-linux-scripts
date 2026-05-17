# Xin Linux Scripts

该项目特色，有意识地基于 python 实现一些常见的脚本。

或许你会发现有更知名更成熟的 shell 脚本，阁下可以选择自己喜欢的方式。

## 常用镜像

### Python

```text
# 官方
https://www.python.org/ftp/python/
# 清华源
https://mirrors.tuna.tsinghua.edu.cn/python/
# 华为源
https://mirrors.huaweicloud.com/python/
```

### PyPI

```text
# 官方
https://pypi.org/simple/
# 清华源
https://pypi.tuna.tsinghua.edu.cn/simple/
# 阿里源
https://mirrors.aliyun.com/pypi/simple/
# 华为源
https://mirrors.huaweicloud.com/repository/pypi/simple/
```

## 脚本

### Install Python

```shell
curl -fsSL https://script.pyth.onl/install_python.sh | bash
# 或
wget -qO- https://script.pyth.onl/install_python.sh | bash
```

### Python Scripts

```shell
# 安装 Docker 环境
curl -fsSL -O https://script.pyth.onl/bin/install_docker.py && python3 install_docker.py

# 开启 BBR
curl -fsSL -O https://script.pyth.onl/bin/enable_bbr.py && python3 enable_bbr.py

# NodeQuality (Python 版)
curl -fsSL -O https://script.pyth.onl/bin/run_nodequality.py && python3 run_nodequality.py
```

