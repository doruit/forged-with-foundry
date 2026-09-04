"""Chainlit entry point for the self-contained PRI-PRE-001 demo."""

import truststore

truststore.inject_into_ssl()

from src.pri_pre_001 import chat as _pri_pre_001_chat  # noqa: E402, F401
