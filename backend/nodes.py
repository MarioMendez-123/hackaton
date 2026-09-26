"""Nodos de visión remotos (la Raspberry Pi con 4 cámaras, ver vision_node/).

El nodo hace la visión pesada y le manda al servidor solo lo que cambió, por
el mismo contrato de eventos de siempre. Aquí vive lo que el servidor sabe de
cada nodo: si está vivo (latido), qué ve cada cámara, las órdenes pendientes
(el nodo pregunta cada segundo; así no hace falta conocer su IP) y el estado
de una búsqueda de objeto repartida entre todas sus cámaras.

Todo en memoria: si el servidor se reinicia, los nodos se vuelven a presentar
en su siguiente latido (cada 5 s).
"""

import hmac
import os
import threading
import time
from collections import deque
from typing import Any

# Sin token configurado se acepta cualquiera (desarrollo en una sola
# computadora). En la red de la casa: DEVICE_TOKEN en .env, igual en el nodo.
DEVICE_TOKEN = os.environ.get("DEVICE_TOKEN", "")
ONLINE_SECONDS = 12  # sin latido en este tiempo = desconectado (el latido es cada 5 s)
SEARCH_TIMEOUT_SECONDS = 25

_lock = threading.Lock()
_nodes: dict[str, dict[str, Any]] = {}
_commands: dict[str, deque] = {}
_search: dict[str, Any] = {"status": "idle"}


def token_ok(token: str | None) -> bool:
    if not DEVICE_TOKEN:
        return True
    return token is not None and hmac.compare_digest(token, DEVICE_TOKEN)


def reset() -> None:
    """Solo para pruebas."""
    with _lock:
        _nodes.clear()
        _commands.clear()
        _search.clear()
        _search["status"] = "idle"


def heartbeat(node_id: str, info: dict[str, Any]) -> None:
    with _lock:
        node = _nodes.setdefault(node_id, {"detections": {}})
        node.update(info)
        node["last_seen"] = time.time()


def set_detections(node_id: str, detections: dict[str, list[dict[str, Any]]]) -> None:
    with _lock:
        node = _nodes.setdefault(node_id, {"detections": {}})
        node["detections"] = detections
        node["last_seen"] = time.time()


def _is_online(node: dict[str, Any]) -> bool:
    return time.time() - node.get("last_seen", 0) <= ONLINE_SECONDS


def online_ids() -> list[str]:
    with _lock:
        return [node_id for node_id, node in _nodes.items() if _is_online(node)]


def any_online() -> bool:
    return bool(online_ids())


def summary() -> list[dict[str, Any]]:
    """Lo que la consola necesita: cámaras de cada nodo, si responde, su
    temperatura y dónde pedir el video."""
    with _lock:
        return [
            {
                "id": node_id,
                "online": _is_online(node),
                "cameras": node.get("cameras", []),
                "stream_url": node.get("stream_url"),
                "temp_c": node.get("temp_c"),
                "seconds_since_seen": round(time.time() - node.get("last_seen", 0), 1),
            }
            for node_id, node in _nodes.items()
        ]


def labels_seen() -> list[dict[str, Any]]:
    """Todas las detecciones de los nodos vivos, con su cámara y zona."""
    out = []
    with _lock:
        for node in _nodes.values():
            if not _is_online(node):
                continue
            zones = {cam.get("id"): cam.get("zone") for cam in node.get("cameras", [])}
            for cam_id, items in node.get("detections", {}).items():
                for item in items:
                    out.append({**item, "camera": cam_id, "zone": zones.get(cam_id)})
    return out


def enqueue(command: dict[str, Any], node_id: str | None = None) -> int:
    """A un nodo, o a todos los que estén vivos. Devuelve a cuántos llegó."""
    targets = [node_id] if node_id else online_ids()
    with _lock:
        for target in targets:
            _commands.setdefault(target, deque(maxlen=50)).append(command)
    return len(targets)


def pop_commands(node_id: str) -> list[dict[str, Any]]:
    with _lock:
        queue = _commands.get(node_id)
        if not queue:
            return []
        items = list(queue)
        queue.clear()
        return items


# ---- búsqueda de objetos en todas las cámaras de los nodos ---------------------


def start_search(label: str, coco_class: str) -> int:
    sent = enqueue({"do": "find", "object": coco_class, "label": label})
    with _lock:
        _search.clear()
        _search.update(status="searching", label=label, target=coco_class, started_at=time.time())
    return sent


def search_found(cam_id: str, zone: str | None, confidence: float) -> bool:
    """El primer nodo que lo ve gana. Devuelve True si cerró la búsqueda."""
    with _lock:
        if _search.get("status") != "searching":
            return False
        _search.update(
            status="found",
            object=_search.get("label"),
            location=zone,
            camera=cam_id,
            confidence=round(confidence, 2),
        )
    enqueue({"do": "cancel_find"})
    return True


def cancel_search() -> None:
    with _lock:
        if _search.get("status") == "searching":
            _search.clear()
            _search["status"] = "idle"
    enqueue({"do": "cancel_find"})


def search_active_or_done() -> bool:
    with _lock:
        return _search.get("status") != "idle"


def search_status() -> dict[str, Any]:
    with _lock:
        if _search.get("status") == "searching" and time.time() - _search["started_at"] > SEARCH_TIMEOUT_SECONDS:
            _search["status"] = "not_found"
        status = dict(_search)
    status.pop("target", None)
    status.pop("started_at", None)
    status.pop("label", None)
    return status
