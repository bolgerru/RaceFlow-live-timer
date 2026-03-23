"""PyInstaller build script for Sailing Race Timer."""

import platform
import subprocess
import sys


def build():
    sep = ";" if platform.system() == "Windows" else ":"
    data_spec = f"public/audio/hooter.mp3{sep}public/audio"

    args = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--name", "SailingTimer",
        "--add-data", data_spec,
        "src/main.py",
    ]

    print(f"Running: {' '.join(args)}")
    subprocess.run(args, check=True)
    print("\nBuild complete! Output is in the dist/SailingTimer/ directory.")


if __name__ == "__main__":
    build()
