#!/usr/bin/env python
"""
Script to run integration tests for tax calculation

This script runs the comprehensive integration test suite that validates
end-to-end tax calculation workflows across different user types and scenarios.

Usage:
    python run_integration_tests.py
    
Or with pytest directly:
    pytest tests/integration/test_tax_calculation_integration.py -v
"""

import subprocess
import sys

def main():
    """Run integration tests with verbose output"""
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/integration/test_tax_calculation_integration.py",
        "-v",
        "--tb=short",
        "--color=yes"
    ]
    
    print("=" * 80)
    print("Running Tax Calculation Integration Tests")
    print("=" * 80)
    print()
    
    result = subprocess.run(cmd, cwd=".")
    
    print()
    print("=" * 80)
    if result.returncode == 0:
        print("✓ All integration tests passed!")
    else:
        print("✗ Some tests failed. See output above for details.")
    print("=" * 80)
    
    return result.returncode

if __name__ == "__main__":
    sys.exit(main())
