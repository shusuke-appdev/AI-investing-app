import os
import subprocess
import sys


def run_command(command, description):
    print(f"\n[Code Factory] Executing: {description}...")
    try:
        # Run command and show output directly to user/agent
        result = subprocess.run(command, shell=True, check=False, text=True)
        if result.returncode != 0:
            print(f"FAILED: {description} failed or found issues.")
            return False
        print(f"PASSED: {description} passed.")
        return True
    except Exception as e:
        print(f"ERROR executing {description}: {e}")
        return False


def main():
    print("Starting Code Factory Lite checks...")

    # Check if tools are installed
    try:
        subprocess.run(["ruff", "--version"], check=True, capture_output=True)
        subprocess.run(["pytest", "--version"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Tools not found. Installing dependencies...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "ruff", "pytest"], check=True
        )

    # 1. Format (Ruff)
    run_command("ruff format .", "Formatting code")

    # 2. Lint & Fix (Ruff)
    lint_success = run_command("ruff check . --fix", "Linting & Fixing code")

    # 3. Test (Pytest)
    if os.path.isdir("tests"):
        test_command = [sys.executable, "-m", "pytest"]
        print(
            f"\n[Code Factory] Executing: Running tests by {' '.join(test_command)}..."
        )
        try:
            subprocess.run(test_command, check=True)
            test_success = True
        except subprocess.CalledProcessError:
            print("FAILED: Running tests failed or found issues.")
            test_success = False
    else:
        print("INFO: 'tests' directory not found. Skipping tests.")
        test_success = True

    if not lint_success or not test_success:
        print("\nChecks completed with issues.")
        sys.exit(1)
    else:
        print("\nAll checks passed! Code is clean.")
        sys.exit(0)


if __name__ == "__main__":
    main()
