"""ASGI app entrypoint expected by openenv validate.

This module provides:
  - `app`: the FastAPI ASGI application
  - `main()`: a runnable entrypoint that starts uvicorn
"""

from __future__ import annotations

import os
from typing import NoReturn

from server import app

import uvicorn


def main() -> NoReturn:
    """Run the ASGI app with uvicorn on the mandated port."""

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "7860"))
    uvicorn.run("server.app:app", host=host, port=port)
    raise SystemExit(0)


if __name__ == "__main__":
    main()

