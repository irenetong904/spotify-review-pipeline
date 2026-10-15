"""Local preview: serves public/ and routes /api/* to the same handler Vercel runs. Reads ../.env for Supabase."""

import os
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "api"))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(HERE.parent / ".env")
import index  # noqa: E402


class Dev(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/api/"):
            return index.handler.do_GET(self)
        return super().do_GET()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8787"))
    ThreadingHTTPServer(("127.0.0.1", port), partial(Dev, directory=str(HERE / "public"))).serve_forever()
