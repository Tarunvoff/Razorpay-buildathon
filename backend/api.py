"""
Legacy entrypoint for RazorGate API.
Re-exports FastAPI `app` from `backend.control.app`.
"""

from backend.control.app import app

__all__ = ["app"]
