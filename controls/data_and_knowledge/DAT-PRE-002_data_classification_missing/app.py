"""Chainlit entry point for the self-contained DAT-PRE-002 demo."""

import truststore

truststore.inject_into_ssl()

from src.dat_pre_002 import chat as _dat_pre_002_chat  # noqa: E402, F401
