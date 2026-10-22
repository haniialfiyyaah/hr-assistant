"""Compatibility entrypoint: ``python -m src.setup_lab``."""

from src.data.setup_lab import ROOT, chunk_policy, main, reset_and_seed

__all__ = ["ROOT", "chunk_policy", "main", "reset_and_seed"]

if __name__ == "__main__":
    main()
