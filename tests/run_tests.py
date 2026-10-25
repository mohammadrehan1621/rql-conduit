"""
RQL CONDUIT — FORMAL INVARIANT AUDIT RUNNER
Principal Architect: Mohammad Rehan • Rehan Quant Lab
Native standalone verification runner for formal mathematical invariants.
"""

import sys
import os
import unittest
import time

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure root directory is on sys.path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from tests.test_conduit import TestRQLConduitInvariants


def run_audit():
    print("=================================================================")
    print(" [*] REHAN QUANT LAB - RQL CONDUIT FORMAL INVARIANT SUITE")
    print(" Verification: Deterministic Multi-Interface Transport Layer")
    print("=================================================================")
    print(f" Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(" Target: Native OS Network Sockets (Zero Kernel Drivers)")
    print("-----------------------------------------------------------------")

    suite = unittest.TestLoader().loadTestsFromTestCase(TestRQLConduitInvariants)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("-----------------------------------------------------------------")
    if result.wasSuccessful():
        print(f" [OK] ALL {result.testsRun} FORMAL INVARIANT TESTS PASSED CLEANLY!")
        print(" Verification Metric: 100% INVARIANTS SATISFIED")
    else:
        print(f" [FAIL] Invariants breached: {len(result.failures)} failures, {len(result.errors)} errors.")
    print("=================================================================")
    if "--no-wait" not in sys.argv and hasattr(sys.stdin, "isatty") and sys.stdin.isatty():
        print("\nPress Enter to close this verification window...")
        try:
            input()
        except Exception:
            pass


if __name__ == "__main__":
    run_audit()
