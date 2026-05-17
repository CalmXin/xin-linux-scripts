import subprocess
import sys
from pathlib import Path


def main():
    work_dir = input(f'请输入脚本运行目录（默认为 /tmp）:')
    work_dir = Path(work_dir or '/tmp')
    if not work_dir.is_dir():
        print(f'{work_dir} 不是一个目录')
        sys.exit(1)

    result = subprocess.run(
        'curl -fsSL https://run.NodeQuality.com | bash',
        shell=True,
        cwd=work_dir
    )
    sys.exit(result.returncode)


if __name__ == '__main__':
    main()
