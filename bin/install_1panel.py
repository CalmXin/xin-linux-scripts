import subprocess
import sys


def main():
    result = subprocess.run(
        'bash -c "$(curl -sSL https://resource.fit2cloud.com/1panel/package/v2/quick_start.sh)"',
        shell=True
    )
    sys.exit(result.returncode)


if __name__ == '__main__':
    main()
