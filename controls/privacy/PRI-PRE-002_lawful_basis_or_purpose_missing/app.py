"""Chainlit entry point for the self-contained PRI-PRE-002 demo."""

import truststore

truststore.inject_into_ssl()

from src.pri_pre_002 import chat as _pri_pre_002_chat  # noqa: E402, F401
