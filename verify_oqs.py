"""Verify that the oqs package and liboqs are available."""

from __future__ import annotations


SETUP_MESSAGE = (
    "Unable to import 'oqs'. Run this project through Docker with "
    "'docker compose run --rm pqc-bench python verify_oqs.py' or "
    "'./run_in_docker.sh python verify_oqs.py'."
)


def main() -> int:
    """Import oqs and print enabled KEM mechanisms when available."""
    try:
        import oqs
    except ImportError:
        print(SETUP_MESSAGE)
        return 1

    try:
        mechanisms = oqs.get_enabled_kem_mechanisms()
    except Exception as exc:  # pragma: no cover - runtime dependency path
        print(f"oqs imported, but querying enabled KEM mechanisms failed: {exc}")
        print("Verify the Docker image built successfully and includes liboqs.")
        return 1

    print("Enabled KEM mechanisms:")
    for mechanism in mechanisms:
        print(f"- {mechanism}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
