import subprocess
import sys


def main():
    result = subprocess.run(
        'curl -fsSL https://rclone.org/install.sh | sudo bash',
        shell=True
    )
    sys.exit(result.returncode)


if __name__ == '__main__':
    main()
