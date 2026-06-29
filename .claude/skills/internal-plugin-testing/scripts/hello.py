"""Throwaway target file for the internal hook-input capture test.

The internal-plugin-testing skill reads this file so the Read PostToolUse
capture hook fires. The content is intentionally trivial.
"""

GREETING = "hello world from internal-plugin-testing"

if __name__ == "__main__":
    print(GREETING)
