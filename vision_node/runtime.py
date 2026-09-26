"""Nodo de visión para la Raspberry Pi: 4 cámaras USB → eventos al servidor.

    python -m vision_node

Configuración: vision_node/cameras.json (qué cámara es cada zona) y variables
de entorno (LUMINA_SERVER_URL, DEVICE_TOKEN, NODE_ID…; ver
vision_node/README.md). Hilos:

- uno de captura por cámara (solo guarda el último cuadro: nunca se atrasa),
- el ciclo principal, que recorre las cámaras por turnos (YOLO solo si algo se
  movió; pose solo donde hay alguien, una cámara a la vez),
- el que manda al servidor (con reintentos para los eventos),
- latido cada 5 s, "qué veo" cada 1 s, órdenes cada 1 s,
- el video MJPEG en el puerto 8001 (solo trabaja si alguien lo está viendo).
"""

import json
import logging
import os
import queue
import socket
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

import cv2

from vision_node.logic import CameraLogic, small_gray

log = logging.getLogger("vision_node")

SERVER = os.environ.get("LUMINA_SERVER_URL", "http://localhost:8000").rstrip("/")
TOKEN = os.environ.get("DEVICE_TOKEN", "")
NODE_ID = os.environ.get("NODE_ID", "pi")
CONFIG = Path(os.environ.get("VISION_CAMERAS", Path(__file__).with_name("cameras.json")))
STREAM_PORT = int(os.environ.get("NODE_STREAM_PORT", "8001"))
# Cómo llega el navegador a la Pi: su IP o "raspberrypi.local".
STREAM_HOST = os.environ.get("NODE_STREAM_HOST", f"{socket.gethostname()}.local")
IMGSZ = int(os.environ.get("NODE_IMGSZ", "320"))
YOLO_MODEL = os.environ.get(
    "NODE_YOLO_MODEL", "yolov8n_ncnn_model" if Path("yolov8n_ncnn_model").exists() else "yolov8n.pt"
)
DETECTION_CONFIDENCE = 0.35
CAPTURE_FPS = 10
STREAM_FPS = 4


# ---------------------------------------------------------------------------
# Red
# ---------------------------------------------------------------------------


def http_json(method: str, path: str, payload: Any = None, timeout: float = 5) -> Any:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        SERVER + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json", "X-Lumina-Token": TOKEN},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read()
    return json.loads(body) if body else None


class Reporter(threading.Thread):
    """Manda al servidor sin frenar la visión. Los eventos (retry=True) se
    reintentan hasta que el servidor responda: si se reinicia, no se pierden.
    Lo que caduca rápido (latido, "qué veo") se descarta si falla."""

    def __init__(self, post: Callable[[str, Any], Any] | None = None, sleep: Callable[[float], None] = time.sleep):
        super().__init__(daemon=True, name="envios")
        self._post = post or (lambda path, payload: http_json("POST", path, payload))
        self._sleep = sleep
        self.queue: queue.Queue = queue.Queue(maxsize=500)

    def send(self, path: str, payload: Any, retry: bool = True) -> None:
        try:
            self.queue.put_nowait((path, payload, retry))
        except queue.Full:
            log.warning("Cola llena: se descarta %s", path)

    def deliver_one(self) -> None:
        path, payload, retry = self.queue.get()
        backoff = 1.0
        while True:
            try:
                self._post(path, payload)
                return
            except Exception as exc:  # red caída, servidor reiniciando…
                if not retry:
                    return
                log.warning("No se pudo enviar %s (%s); reintento en %.0f s", path, exc, backoff)
                self._sleep(backoff)
                backoff = min(backoff * 2, 15)

    def run(self) -> None:
        while True:
            self.deliver_one()


# ---------------------------------------------------------------------------
# Cámaras
# ---------------------------------------------------------------------------


class Capture(threading.Thread):
    """Lee una cámara sin parar y guarda solo el último cuadro."""

    def __init__(self, cam_id: str, device: int | str) -> None:
        super().__init__(daemon=True, name=f"captura-{cam_id}")
        self.cam_id = cam_id
        self.device = device
        self.frames = 0
        self._frame = None
        self._frame_at = 0.0
        self._lock = threading.Lock()

    def _open(self) -> cv2.VideoCapture:
        cap = cv2.VideoCapture(self.device, cv2.CAP_V4L2) if os.name != "nt" else cv2.VideoCapture(self.device)
        # MJPEG 640x480 a 10 cps: menos USB y menos trabajo de descompresión.
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, CAPTURE_FPS)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        return cap

    def run(self) -> None:
        cv2.setNumThreads(1)
        while True:
            cap = self._open()
            while cap.isOpened():
                ok, frame = cap.read()
                if not ok:
                    break
                with self._lock:
                    self._frame, self._frame_at = frame, time.time()
                self.frames += 1
            cap.release()
            log.warning("Cámara %s sin señal; reintento en 3 s", self.cam_id)
            time.sleep(3)

    def latest(self):
        with self._lock:
            return self._frame, self._frame_at


class Detector:
    """YOLOv8n (NCNN en la Pi si se exportó; si no, el .pt)."""

    def __init__(self) -> None:
        from ultralytics import YOLO

        self.model = YOLO(YOLO_MODEL, task="detect")
        log.info("YOLO: %s a %d px", YOLO_MODEL, IMGSZ)

    def __call__(self, frame) -> list[dict[str, Any]]:
        result = self.model(frame, imgsz=IMGSZ, verbose=False)[0]
        names = self.model.names
        out = []
        for box in result.boxes:
            confidence = float(box.conf[0])
            if confidence >= DETECTION_CONFIDENCE:
                out.append(
                    {
                        "label": names[int(box.cls[0])],
                        "confidence": confidence,
                        "box": [int(v) for v in box.xyxy[0]],
                    }
                )
        return out


def cpu_temperature() -> float | None:
    try:
        return int(Path("/sys/class/thermal/thermal_zone0/temp").read_text()) / 1000
    except (OSError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Video en vivo (MJPEG)
# ---------------------------------------------------------------------------


def draw(frame, logic: CameraLogic):
    out = frame.copy()
    for d in logic.boxes:
        x1, y1, x2, y2 = d["box"]
        color = (255, 209, 201) if d["label"] == "person" else (195, 160, 154)
        cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
    return out


def make_stream_handler(captures: dict[str, Capture], logics: dict[str, CameraLogic]):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # sin ruido en la terminal
            pass

        def do_GET(self):
            parts = self.path.strip("/").split("/")
            if parts == ["health"]:
                body = json.dumps({cam: cap.latest()[0] is not None for cam, cap in captures.items()}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
                return
            if len(parts) != 2 or parts[0] not in ("stream", "snapshot") or parts[1] not in captures:
                self.send_error(404)
                return
            cam_id = parts[1]
            if parts[0] == "snapshot":
                frame, _ = captures[cam_id].latest()
                if frame is None:
                    self.send_error(503)
                    return
                ok, jpeg = cv2.imencode(".jpg", draw(frame, logics[cam_id]), [cv2.IMWRITE_JPEG_QUALITY, 75])
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.end_headers()
                self.wfile.write(jpeg.tobytes())
                return
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            try:
                while True:
                    frame, _ = captures[cam_id].latest()
                    if frame is not None:
                        ok, jpeg = cv2.imencode(".jpg", draw(frame, logics[cam_id]), [cv2.IMWRITE_JPEG_QUALITY, 70])
                        if ok:
                            self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n")
                    time.sleep(1 / STREAM_FPS)
            except (BrokenPipeError, ConnectionResetError):
                return  # el navegador cerró el video

    return Handler


# ---------------------------------------------------------------------------
# Principal
# ---------------------------------------------------------------------------


def every(seconds: float, fn: Callable[[], None], name: str) -> None:
    def loop():
        while True:
            try:
                fn()
            except Exception as exc:
                log.warning("%s falló: %s", name, exc)
            time.sleep(seconds)

    threading.Thread(target=loop, daemon=True, name=name).start()


def main() -> None:
    cameras = json.loads(CONFIG.read_text(encoding="utf-8"))
    captures = {c["id"]: Capture(c["id"], c["device"]) for c in cameras}
    logics = {c["id"]: CameraLogic(c["id"], c["zone"], c.get("tasks", []), NODE_ID) for c in cameras}
    inferences = {cam_id: 0 for cam_id in captures}
    search = {"target": None}
    search_lock = threading.Lock()

    for capture in captures.values():
        capture.start()
    reporter = Reporter()
    reporter.start()

    detector = Detector()
    pose = None
    if any("falls" in logic.tasks for logic in logics.values()):
        from backend.vision import _get_pose

        pose = _get_pose()
        log.info("Caídas: %s", "MediaPipe listo" if pose else "sin MediaPipe (no se detectan caídas)")
    from backend.vision import torso_from_pose

    server = ThreadingHTTPServer(("0.0.0.0", STREAM_PORT), make_stream_handler(captures, logics))
    threading.Thread(target=server.serve_forever, daemon=True, name="video").start()
    log.info("Video en http://%s:%d/stream/<cámara>", STREAM_HOST, STREAM_PORT)

    last_counts = {cam_id: 0 for cam_id in captures}
    last_inferences = dict(inferences)

    def heartbeat():
        cams = []
        for cam in cameras:
            cam_id = cam["id"]
            frame, at = captures[cam_id].latest()
            cams.append(
                {
                    "id": cam_id,
                    "zone": cam["zone"],
                    "ok": frame is not None and time.time() - at < 3,
                    "fps": round((captures[cam_id].frames - last_counts[cam_id]) / 5, 1),
                    "analysis_per_s": round((inferences[cam_id] - last_inferences[cam_id]) / 5, 2),
                }
            )
            last_counts[cam_id] = captures[cam_id].frames
            last_inferences[cam_id] = inferences[cam_id]
        payload = {"cameras": cams, "stream_url": f"http://{STREAM_HOST}:{STREAM_PORT}", "temp_c": cpu_temperature()}
        reporter.send(f"/vision/nodes/{NODE_ID}/heartbeat", payload, retry=False)

    def detections():
        reporter.send(
            f"/vision/nodes/{NODE_ID}/detections",
            {cam_id: logic.detections for cam_id, logic in logics.items()},
            retry=False,
        )

    def commands():
        for command in http_json("GET", f"/vision/nodes/{NODE_ID}/commands")["commands"]:
            action = command.get("do")
            log.info("Orden: %s", command)
            with search_lock:
                if action == "find":
                    search["target"] = command["object"]
                elif action == "cancel_find":
                    search["target"] = None
            if action == "calibrate_door":
                for logic in logics.values():
                    logic.request_calibration()

    heartbeat()
    every(5, heartbeat, "latido")
    every(1, detections, "detecciones")
    every(1, commands, "ordenes")

    while True:
        for cam_id, logic in logics.items():
            frame, at = captures[cam_id].latest()
            now = time.time()
            if frame is None or now - at > 2:
                continue
            small = small_gray(frame)
            events = logic.door_update(small, now)
            if logic.needs_inference(small, now):
                found = detector(frame)
                inferences[cam_id] += 1
                events += logic.on_detections(found, now)
                with search_lock:
                    target = search["target"]
                if target:
                    confidence = logic.found(found, target)
                    if confidence is not None:
                        with search_lock:
                            search["target"] = None
                        reporter.send(
                            f"/vision/nodes/{NODE_ID}/found",
                            {"camera": cam_id, "zone": logic.zone, "confidence": confidence},
                        )
            if pose is not None and logic.wants_pose(now):
                events += logic.fall_update(torso_from_pose(frame, pose), now)
            for event in events:
                log.info("Evento %s en %s", event["type"], cam_id)
                reporter.send(f"/vision/nodes/{NODE_ID}/events", event)
        time.sleep(0.01)
