"""Chainlit entry point for the self-contained PRI-004 demo."""

import truststore

truststore.inject_into_ssl()

from src.pri_004 import chat as _pri_004_chat  # noqa: E402, F401
