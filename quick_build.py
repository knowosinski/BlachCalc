#!/usr/bin/env python3
"""Build BlachCalc v1.4.1 - invoke Build-Windows.ps1 via Python subprocess."""
import subprocess
import sys
from pathlib import Path

def main():
    repo = Path(__file__).parent
    build_script = repo / "Build-Windows.ps1"
    
    if not build_script.exists():
        print(f"❌ BUILD SCRIPT NOT FOUND: {build_script}")
        return False
    
    print(f"📦 Building BlachCalc v1.4.1 from: {repo}")
    print(f"🔧 Build script: {build_script}")
    print("=" * 70)
    print()
    
    try:
        # Try to run Build-Windows.ps1 directly
        proc = subprocess.Popen(
            ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", str(build_script)],
            cwd=str(repo),
        )
        retcode = proc.wait()
        
        if retcode == 0:
            print()
            print("=" * 70)
            print("✅ BUILD SUCCESSFUL")
            print("=" * 70)
            print(f"📍 Installer: {repo / 'release' / 'BlachCalc-Setup.exe'}")
            print(f"📍 App:       {repo / 'dist' / 'BlachCalc' / 'BlachCalc.exe'}")
            return True
        else:
            print()
            print("=" * 70)
            print(f"❌ BUILD FAILED (exit code {retcode})")
            print("=" * 70)
            return False
    
    except FileNotFoundError:
        print("❌ powershell.exe NOT FOUND")
        return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

if __name__ == "__main__":
    sys.exit(0 if main() else 1)
