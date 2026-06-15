import subprocess
import sys


def main():
    result = subprocess.run(
        'curl -LsSf https://astral.sh/uv/install.sh | sh',
        shell=True
    )
    sys.exit(result.returncode)


if __name__ == '__main__':
    main()
