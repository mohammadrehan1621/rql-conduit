"""
RQL CONDUIT — MAIN ENTRY POINT
Principal Architect: Mohammad Rehan • Rehan Quant Lab
Dual-WAN Zero-Cloud Network Bonding Engine.
"""

import sys
import os

# Ensure local directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gui import RQLConduitGUI


def main():
    app = RQLConduitGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
