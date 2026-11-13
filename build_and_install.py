#!/usr/bin/env python3
"""Build BlachCalc and install it."""
import subprocess
import sys
from pathlib import Path

def run_command(cmd, description):
    """Run command and report status."""
    print(f"\n{'='*60}")
    print(f"▶ {description}")
    print(f"{'='*60}")
    try:
        result = subprocess.run(cmd, shell=True, timeout=1800)
        if result.returncode == 0:
            print(f"✅ {description}: OK")
            return True
        else:
            print(f"❌ {description}: FAILED (exit code {result.returncode})")
            return False
    except subprocess.TimeoutExpired:
        print(f"❌ {description}: TIMEOUT (30 minut)")
        return False
    except Exception as e:
        print(f"❌ {description}: ERROR: {e}")
        return False

def main():
    repo_root = Path(__file__).parent
    
    # Step 1: Build
    print("\n" + "="*60)
    print("📦 BLACHCALC BUILD & INSTALL v1.4.1")
    print("="*60)
    
    build_script = repo_root / "Build-Windows.ps1"
    if not build_script.exists():
        print(f"❌ Build script not found: {build_script}")
        return False
    
    build_ok = run_command(
        f'powershell -ExecutionPolicy Bypass -File "{build_script}"',
        "Building BlachCalc v1.4.1"
    )
    
    if not build_ok:
        print("\n⚠️  Build failed. Stopping.")
        return False
    
    # Step 2: Find installer
    installer = None
    candidates = [
        repo_root / "release" / "BlachCalc-Setup.exe",
        repo_root / "BlachCalc-Setup.exe",
    ]
    for candidate in candidates:
        if candidate.is_file():
            installer = candidate
            break
    
    if not installer:
        print(f"❌ Installer not found in:")
        for c in candidates:
            print(f"   - {c}")
        return False
    
    print(f"\n✅ Found installer: {installer}")
    
    # Step 3: Install
    install_ok = run_command(
        f'"{installer}" /SILENT /NORESTART /CLOSEAPPLICATIONS',
        "Installing BlachCalc (silent mode)"
    )
    
    if not install_ok:
        print("\n⚠️  Installation failed.")
        return False
    
    print("\n" + "="*60)
    print("✅ BUILD & INSTALL COMPLETE")
    print("="*60)
    print(f"\n📍 Installation folder: C:\\Users\\{Path.home().name}\\AppData\\Local\\Programs\\BlachCalc")
    print(f"📍 Data folder: C:\\Users\\{Path.home().name}\\Documents\\BLACHCALC")
    print("\n🎉 BlachCalc v1.4.1 is ready to use!")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
