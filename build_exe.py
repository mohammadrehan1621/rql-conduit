"""
RQL CONDUIT — STANDALONE EXECUTABLE COMPILER
Principal Architect: Mohammad Rehan • Rehan Quant Lab
Packages RQLConduit.exe as a zero-dependency native Windows binary.
"""

import os
import sys
import subprocess
import shutil

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

def build():
    print("=================================================================")
    print(" [*] COMPILING RQL CONDUIT INTO STANDALONE .EXE")
    print(" Rehan Quant Lab - Sovereign Systems Architecture")
    print("=================================================================")

    # Change to root directory
    os.chdir(ROOT_DIR)

    # Command parameters for Primary Workstation GUI
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconsole",
        "--onefile",
        "--name", "RQLConduit",
        "--add-binary", f"{os.path.join(ROOT_DIR, 'rql_conduit_core.dll')};.",
        "--collect-all", "customtkinter",
        "--clean",
        "main.py"
    ]

    print(f"[1/3] Executing PyInstaller: {' '.join(cmd)}")
    result = subprocess.run(cmd)

    if result.returncode != 0:
        print("[!] Build failed with return code:", result.returncode)
        sys.exit(result.returncode)

    # Copy binary to root folder for 1-click access
    dist_exe = os.path.join(ROOT_DIR, "dist", "RQLConduit.exe")
    target_exe = os.path.join(ROOT_DIR, "RQLConduit.exe")

    if os.path.exists(dist_exe):
        shutil.copy2(dist_exe, target_exe)
        file_size_mb = os.path.getsize(target_exe) / (1024 * 1024)
        print("=================================================================")
        print(f" [OK] BUILD COMPLETE! Native Workstation Binary Ready:")
        print(f" Path: {target_exe}")
        print(f" Size: {file_size_mb:.2f} MB")
        print("=================================================================")
    else:
        print("[!] Could not locate compiled dist/RQLConduit.exe")

    # Command parameters for Invariant Test Runner CLI
    cmd_runner = [
        sys.executable, "-m", "PyInstaller",
        "--console",
        "--onefile",
        "--name", "RQLConduit-TestRunner",
        "--add-binary", f"{os.path.join(ROOT_DIR, 'rql_conduit_core.dll')};.",
        "--clean",
        os.path.join("tests", "run_tests.py")
    ]
    print(f"[2/3] Compiling Test Runner: {' '.join(cmd_runner)}")
    result_runner = subprocess.run(cmd_runner)
    if result_runner.returncode == 0:
        dist_runner = os.path.join(ROOT_DIR, "dist", "RQLConduit-TestRunner.exe")
        target_runner = os.path.join(ROOT_DIR, "RQLConduit-TestRunner.exe")
        if os.path.exists(dist_runner):
            shutil.copy2(dist_runner, target_runner)
            runner_mb = os.path.getsize(target_runner) / (1024 * 1024)
            print(f" [OK] Invariant Test Runner Ready: {target_runner} ({runner_mb:.2f} MB)")

if __name__ == "__main__":
    build()
