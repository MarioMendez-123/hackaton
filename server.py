"""Servidor mínimo para correr Lumina sola: python server.py  ->  http://localhost:8000"""

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path


def _load_local_env(path: Path = Path(__file__).parent / ".env") -> None:
    """Configuración local (n8n, número de alertas, claves) sin subirla a
    GitHub: .env está en .gitignore; .env.example dice qué va. No pisa lo que
    ya venga del sistema. En pytest no se carga: las pruebas usan simulados."""
    if "pytest" in sys.modules or not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"'))


_load_local_env()  # antes de importar backend/: lee las variables al importarse

from fastapi import FastAPI  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from backend.api import router as backend_router  # noqa: E402
from backend.api import start_fall_watchdog  # noqa: E402
from lumina import router  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_fall_watchdog()  # avisa al contacto si nadie contesta tras una caída
    yield


app = FastAPI(lifespan=lifespan)


@app.middleware("http")
async def revalidate_static(request, call_next):
    """Sin esto el navegador se queda con CSS/JS viejos tras cada cambio.
    no-cache no quita la caché: revalida con ETag y responde 304 si nada cambió."""
    response = await call_next(request)
    response.headers.setdefault("Cache-Control", "no-cache")
    return response


app.include_router(router)
app.include_router(backend_router)
# Montado al final: las rutas de arriba se resuelven primero.
app.mount("/", StaticFiles(directory=Path(__file__).parent / "web", html=True), name="web")

if __name__ == "__main__":
    import uvicorn

    # En la red de la casa (Raspberry, ESP32, otras pantallas): LUMINA_HOST=0.0.0.0
    # en .env. Por defecto solo esta computadora.
    uvicorn.run(app, host=os.environ.get("LUMINA_HOST", "127.0.0.1"), port=int(os.environ.get("LUMINA_PORT", "8000")))
