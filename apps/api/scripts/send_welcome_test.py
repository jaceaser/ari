"""Send a sample welcome email to the given addresses.

Usage:
    python scripts/send_welcome_test.py

Requires AZURE_COMMUNICATION_ENDPOINT (and optionally AZURE_COMMUNICATION_SENDER)
to be set in the environment, or in apps/api/.env.
"""

import asyncio
import os
import sys

# Allow importing from apps/api
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Load .env if present
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "../.env"))
except ImportError:
    pass

RECIPIENTS = [
    "joshua@enov8nexus.com",
    "joshua.a.ceaser@gmail.com",
]


async def main():
    from routes.magic_link import send_welcome_email

    endpoint = os.getenv("AZURE_COMMUNICATION_ENDPOINT", "")
    if not endpoint:
        print("ERROR: AZURE_COMMUNICATION_ENDPOINT is not set.")
        sys.exit(1)

    for email in RECIPIENTS:
        print(f"Sending welcome email to {email}...")
        try:
            await send_welcome_email(email)
            print(f"  ✓ Sent to {email}")
        except Exception as exc:
            print(f"  ✗ Failed for {email}: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
