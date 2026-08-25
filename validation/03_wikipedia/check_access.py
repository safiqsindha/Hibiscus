"""Validation 3 (blocked): attempted access check for Wikipedia quality
classes.

This script exists to document the environment constraint, not to run the
validation -- see FINDINGS.md. It re-checks (without retrying in a loop,
per this sandbox's proxy guidance) whether the hosts a Wikipedia pull would
need are reachable, and prints the proxy's own diagnostic for each.
"""

from __future__ import annotations

import subprocess

HOSTS_NEEDED = [
    "en.wikipedia.org",       # MediaWiki API (article prose)
    "dumps.wikimedia.org",    # bulk XML dumps (alternative to live API)
    "wikimedia.org",
]

ALREADY_CONFIRMED_REACHABLE = [
    "raw.githubusercontent.com / github.com (via this session's git proxy)",
    "storage.googleapis.com (used for the SummEval data in ../02_summeval)",
]


def check(host: str) -> str:
    result = subprocess.run(
        ["curl", "-sS", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", "10", f"https://{host}"],
        capture_output=True, text=True,
    )
    return result.stdout.strip() or f"(curl error: {result.stderr.strip()[:200]})"


def main() -> None:
    print("Hosts a live Wikipedia quality-class pull would need:")
    for host in HOSTS_NEEDED:
        print(f"  {host}: {check(host)}")
    print()
    print("Hosts already confirmed reachable in this sandbox (used elsewhere in this validation):")
    for host in ALREADY_CONFIRMED_REACHABLE:
        print(f"  {host}")
    print()
    proxy_status = subprocess.run(
        ["curl", "-sS", "--max-time", "10", "http://127.0.0.1:46023/__agentproxy/status"],
        capture_output=True, text=True,
    ).stdout
    print("Proxy status (recentRelayFailures shows the policy denial):")
    print(proxy_status)


if __name__ == "__main__":
    main()
