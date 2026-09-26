"""Visión (Bloque 5 / sección 11: backend/vision) — CameraProvider desacoplado.

Hoy: una webcam local + YOLOv8n (COCO, 80 clases) para personas/objetos +
MediaPipe Pose para postura de caída + diferencia de frames para la puerta.
El día que haya cámara/AWS real de por medio, se reemplaza esta clase sin
tocar `agent.py` ni `api.py`: todo lo que detecta sale por el MISMO contrato
de eventos de la sección 12 (`memory.save_event` + `agent.apply_event`),
igual que si viniera de un ESP32.

Modelos pesados (YOLO, MediaPipe) se cargan solo al arrancar la cámara
(`start()`), nunca al importar este módulo — así los tests y el resto del
backend no pagan ese costo ni requieren webcam.
"""

import math
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any

import cv2
import numpy as np

try:
    import mediapipe as mp
except ImportError:  # p. ej. una Raspberry donde no instaló: sin caídas, lo demás sigue
    mp = None

from backend import agent, memory
from backend.events import EventIn

CAMERA_INDEX = int(os.environ.get("CAMERA_INDEX", "0"))
# Con una sola webcam de hackathon, el "dónde está apuntando" se decide en
# demo (cocina para el escenario de riesgo, puerta para el de seguridad).
CAMERA_LOCATION = os.environ.get("CAMERA_LOCATION", "kitchen")
YOLO_WEIGHTS = os.environ.get("YOLO_WEIGHTS", "yolov8n.pt")
YOLO_CONF_THRESHOLD = float(os.environ.get("YOLO_CONF_THRESHOLD", "0.5"))

# MediaPipe Tasks API (>=0.10): la API legacy `mp.solutions.pose` ya no
# existe en el paquete instalado (solo trae `mediapipe.tasks`). El .task se
# descarga una vez a mano (ver README) y se cachea en el repo, igual que
# yolov8n.pt.
POSE_MODEL_PATH = os.environ.get("POSE_MODEL_PATH", "pose_landmarker_lite.task")
POSE_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
    "pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
)

# ponytail: umbral fijo sin calibrar contra la iluminación real del evento.
# Recalibrar (o hacerlo relativo al brillo promedio de la escena) si la
# puerta da falsos positivos en sitio.
DOOR_DIFF_THRESHOLD = float(os.environ.get("DOOR_DIFF_THRESHOLD", "18.0"))

# ponytail: heurística geométrica con MediaPipe Pose, no un clasificador de
# caídas entrenado. Caída = las tres cosas a la vez (ver FallDetector):
# de pie -> torso horizontal RÁPIDO, la cadera baja de golpe en la imagen, y
# se queda abajo. Acostarse despacio, acostarse desde sentado (la cadera casi
# no baja) o agacharse y levantarse no cuentan. Todos ajustables por env.
FALL_ANGLE_DEGREES = float(os.environ.get("FALL_ANGLE_DEGREES", "55"))  # torso a esto o más: horizontal
FALL_UPRIGHT_DEGREES = float(os.environ.get("FALL_UPRIGHT_DEGREES", "30"))  # a esto o menos: de pie
FALL_FAST_SECONDS = float(os.environ.get("FALL_FAST_SECONDS", "1.5"))  # de pie a horizontal en menos de esto
FALL_MIN_DROP = float(os.environ.get("FALL_MIN_DROP", "0.12"))  # la cadera baja al menos 12% del alto de la imagen
FALL_STAY_DOWN_SECONDS = float(os.environ.get("FALL_STAY_DOWN_SECONDS", "2.5"))  # y se queda abajo esto
FALL_COOLDOWN_SECONDS = 30  # no repetir el mismo aviso

SEARCH_TIMEOUT_SECONDS = 20
SEARCH_HOLD_SECONDS = 5  # cuánto sigue resaltado el objeto tras encontrarlo

# Español -> clase real de COCO (las 80 que ve yolov8n). COCO no tiene
# "llaves" ni "cartera" como clase: para esas, la fuente confiable sigue
# siendo memory.py (evento manual u otra cámara), nunca una clase inventada.
OBJECT_NAME_MAP = {
    "celular": "cell phone",
    "telefono": "cell phone",
    "teléfono": "cell phone",
    "control": "remote",
    "control remoto": "remote",
    "mochila": "backpack",
    "bolsa": "handbag",
    "bolso": "handbag",
    "maleta": "suitcase",
    "laptop": "laptop",
    "computadora": "laptop",
    "libro": "book",
    "botella": "bottle",
    "taza": "cup",
    "reloj": "clock",
    "tijeras": "scissors",
    "paraguas": "umbrella",
}

# Lo que la consola ofrece como atajos de búsqueda: un nombre por objeto (sin
# los sinónimos de arriba, que existen para que la VOZ los entienda).
SEARCHABLE_OBJECTS = (
    "celular",
    "mochila",
    "control",
    "laptop",
    "libro",
    "botella",
    "taza",
    "reloj",
    "bolsa",
    "maleta",
    "tijeras",
    "paraguas",
)

# Nombre en español de lo que YOLO ve, solo para mostrarlo ("Veo: persona,
# taza"). Lo que no está aquí se muestra con su nombre de COCO tal cual.
COCO_LABELS_ES = {
    "person": "persona",
    "cell phone": "celular",
    "remote": "control",
    "backpack": "mochila",
    "handbag": "bolsa",
    "suitcase": "maleta",
    "laptop": "laptop",
    "book": "libro",
    "bottle": "botella",
    "cup": "taza",
    "clock": "reloj",
    "scissors": "tijeras",
    "umbrella": "paraguas",
    "chair": "silla",
    "couch": "sillón",
    "bed": "cama",
    "dining table": "mesa",
    "tv": "televisión",
    "keyboard": "teclado",
    "mouse": "mouse",
    "oven": "horno",
    "microwave": "microondas",
    "refrigerator": "refrigerador",
    "sink": "fregadero",
    "toaster": "tostador",
    "bowl": "tazón",
    "knife": "cuchillo",
    "spoon": "cuchara",
    "fork": "tenedor",
    "wine glass": "copa",
    "potted plant": "planta",
    "vase": "florero",
    "cat": "gato",
    "dog": "perro",
    "teddy bear": "peluche",
    "toothbrush": "cepillo de dientes",
}

_POSE_SHOULDER_L, _POSE_SHOULDER_R = 11, 12
_POSE_HIP_L, _POSE_HIP_R = 23, 24

_yolo_model = None
_pose_model = None


def _get_yolo():
    global _yolo_model
    if _yolo_model is None:
        from ultralytics import YOLO

        _yolo_model = YOLO(YOLO_WEIGHTS)
    return _yolo_model


def _get_pose():
    """None si MediaPipe no está instalado: la cámara sigue, sin caídas."""
    global _pose_model
    if mp is None:
        return None
    if _pose_model is None:
        import urllib.request

        from mediapipe.tasks.python import vision as mp_vision
        from mediapipe.tasks.python.core.base_options import BaseOptions

        if not os.path.exists(POSE_MODEL_PATH):
            urllib.request.urlretrieve(POSE_MODEL_URL, POSE_MODEL_PATH)

        options = mp_vision.PoseLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=POSE_MODEL_PATH),
            min_pose_detection_confidence=0.5,
        )
        _pose_model = mp_vision.PoseLandmarker.create_from_options(options)
    return _pose_model


# ---------------------------------------------------------------------------
# Heurísticas puras (testeables sin cámara ni modelos)
# ---------------------------------------------------------------------------


def map_object_name(spanish_name: str) -> str | None:
    return OBJECT_NAME_MAP.get(spanish_name.strip().lower())


def mean_gray_diff(frame_a: np.ndarray, frame_b: np.ndarray) -> float:
    """Qué tan distinta es una imagen en escala de grises de otra (0 = igual)."""
    if frame_a.shape != frame_b.shape:
        return 0.0
    return float(np.mean(cv2.absdiff(frame_a, frame_b)))


def door_state_from_diff(diff_score: float) -> str:
    return "open" if diff_score >= DOOR_DIFF_THRESHOLD else "closed"


def fall_angle_from_points(shoulder_mid: tuple[float, float], hip_mid: tuple[float, float]) -> float:
    """Ángulo del torso respecto a la vertical, en grados: 0° de pie, cerca
    de 90° acostado."""
    dx = shoulder_mid[0] - hip_mid[0]
    dy = shoulder_mid[1] - hip_mid[1]
    return math.degrees(math.atan2(abs(dx), abs(dy) + 1e-6))


def is_fallen_posture(shoulder_mid: tuple[float, float], hip_mid: tuple[float, float]) -> bool:
    return fall_angle_from_points(shoulder_mid, hip_mid) >= FALL_ANGLE_DEGREES


def torso_from_pose(frame: np.ndarray, pose) -> tuple[float, float] | None:
    """(ángulo del torso, altura de la cadera 0-1) de la persona que MediaPipe
    ve, o None si no hay nadie. Lo usan la cámara local y el nodo de la
    Raspberry (vision_node), así las caídas se deciden igual en los dos."""
    height, width = frame.shape[:2]
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    result = pose.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
    if not result.pose_landmarks:
        return None
    lm = result.pose_landmarks[0]
    shoulder_mid = (
        (lm[_POSE_SHOULDER_L].x + lm[_POSE_SHOULDER_R].x) / 2 * width,
        (lm[_POSE_SHOULDER_L].y + lm[_POSE_SHOULDER_R].y) / 2 * height,
    )
    hip_mid = (
        (lm[_POSE_HIP_L].x + lm[_POSE_HIP_R].x) / 2 * width,
        (lm[_POSE_HIP_L].y + lm[_POSE_HIP_R].y) / 2 * height,
    )
    return fall_angle_from_points(shoulder_mid, hip_mid), hip_mid[1] / height


class FallDetector:
    """Decide "caída" frame a frame con tiempo real, no con N frames seguidos
    (antes, acostarse en el sillón o agacharse un rato la disparaban).

    update(t, angle, hip_y): t en segundos, angle del torso (0° de pie, 90°
    acostado), hip_y = altura de la cadera normalizada (0 arriba, 1 abajo,
    como da MediaPipe). Devuelve True una sola vez por caída."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._upright_at: float | None = None
        self._upright_hip_y: float | None = None
        self._down_since: float | None = None
        self._looks_like_fall = False
        self._reported = False

    def update(self, t: float, angle: float, hip_y: float) -> bool:
        if angle <= FALL_UPRIGHT_DEGREES:
            # De pie otra vez: se olvida lo anterior y se puede volver a avisar.
            self._upright_at, self._upright_hip_y = t, hip_y
            self._down_since, self._looks_like_fall, self._reported = None, False, False
            return False
        if angle < FALL_ANGLE_DEGREES:
            return False  # a medio camino (agachándose, sentándose): no decide nada todavía
        if self._down_since is None:
            self._down_since = t
            came_from_upright = self._upright_at is not None and t - self._upright_at <= FALL_FAST_SECONDS
            dropped = self._upright_hip_y is not None and hip_y - self._upright_hip_y >= FALL_MIN_DROP
            self._looks_like_fall = came_from_upright and dropped
        if self._looks_like_fall and not self._reported and t - self._down_since >= FALL_STAY_DOWN_SECONDS:
            self._reported = True
            return True
        return False


# ---------------------------------------------------------------------------
# CameraProvider
# ---------------------------------------------------------------------------


class LocalCameraProvider:
    def __init__(self) -> None:
        self._cap: cv2.VideoCapture | None = None
        self._thread: threading.Thread | None = None
        self._running = False
        self._lock = threading.Lock()

        self._latest_jpeg: bytes | None = None
        self._last_frame_gray: np.ndarray | None = None

        self._door_baseline: np.ndarray | None = None
        self._last_door_state: str | None = None
        self._last_occupancy_state: str | None = None

        self._fall_detector = FallDetector()
        self._last_fall_notified_at = 0.0

        self._search_target: str | None = None
        self._search_label: str | None = None
        self._search_started_at = 0.0
        self._search_status = "idle"  # idle | searching | found | not_found
        self._search_result: dict[str, Any] = {}
        self._found_class: str | None = None
        self._found_until = 0.0

        self._last_detections: list[dict[str, Any]] = []

    def is_running(self) -> bool:
        return self._running

    def get_detections(self) -> list[dict[str, Any]]:
        """Lo que YOLO vio en el último cuadro, en español — vacío si la
        cámara está apagada (no se muestra lo último que vio como si fuera ahora)."""
        with self._lock:
            return list(self._last_detections) if self._running else []

    def start(self) -> None:
        if self._running:
            return
        cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)
        if not cap.isOpened():
            raise RuntimeError(f"No se pudo abrir la cámara {CAMERA_INDEX}.")
        self._cap = cap
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def get_latest_jpeg(self) -> bytes | None:
        with self._lock:
            return self._latest_jpeg

    def calibrate_door(self) -> bool:
        with self._lock:
            if self._last_frame_gray is None:
                return False
            self._door_baseline = self._last_frame_gray.copy()
        return True

    def start_search(self, spanish_name: str) -> dict[str, Any]:
        target = map_object_name(spanish_name)
        if target is None:
            return {"ok": False, "supported": sorted(set(OBJECT_NAME_MAP))}
        with self._lock:
            self._search_target = target
            self._search_label = spanish_name.strip()
            self._search_started_at = time.time()
            self._search_status = "searching"
            self._search_result = {}
        return {"ok": True}

    def reset(self) -> None:
        """Solo para tests: limpia calibración/búsqueda sin tocar la cámara física."""
        with self._lock:
            self._door_baseline = None
            self._last_door_state = None
            self._last_occupancy_state = None
            self._fall_detector.reset()
            self._last_fall_notified_at = 0.0
            self._search_target = None
            self._search_label = None
            self._search_status = "idle"
            self._search_result = {}
            self._found_class = None
            self._found_until = 0.0
            self._last_detections = []

    def cancel_search(self) -> None:
        """Comando de voz "Lumina, cancela": corta la búsqueda en curso sin
        esperar el timeout de 20s."""
        with self._lock:
            if self._search_status == "searching":
                self._search_status = "idle"
                self._search_target = None
                self._search_result = {}

    def get_search_status(self) -> dict[str, Any]:
        with self._lock:
            if self._search_status == "searching" and time.time() - self._search_started_at > SEARCH_TIMEOUT_SECONDS:
                self._search_status = "not_found"
                self._search_target = None
            return {"status": self._search_status, **self._search_result}

    # -- ciclo principal ----------------------------------------------------

    def _loop(self) -> None:
        yolo = _get_yolo()
        pose = _get_pose()
        while self._running:
            ok, frame = self._cap.read()
            if not ok:
                time.sleep(0.1)
                continue

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            self._last_frame_gray = gray

            person_present = self._detect_and_draw(frame, yolo)
            self._apply_occupancy(person_present)
            self._apply_door_state(gray)
            if pose is not None:
                self._apply_fall_detection(frame, pose)

            ok_jpeg, buf = cv2.imencode(".jpg", frame)
            if ok_jpeg:
                with self._lock:
                    self._latest_jpeg = buf.tobytes()

            time.sleep(0.03)

    def _detect_and_draw(self, frame: np.ndarray, yolo) -> bool:
        results = yolo(frame, verbose=False)[0]
        person_present = False
        found_now: tuple[str, float] | None = None
        detections: list[dict[str, Any]] = []

        with self._lock:
            searching_for = self._search_target if self._search_status == "searching" else None
            found_class = self._found_class if time.time() < self._found_until else None

        for box in results.boxes:
            cls_name = yolo.names[int(box.cls[0])]
            conf = float(box.conf[0])
            if conf < YOLO_CONF_THRESHOLD:
                continue
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            label_es = COCO_LABELS_ES.get(cls_name, cls_name)
            detections.append({"label": label_es, "confidence": round(conf, 2)})

            if cls_name == "person":
                person_present = True

            is_target = cls_name == searching_for
            is_recently_found = cls_name == found_class
            if is_target:
                found_now = (cls_name, conf)

            # BGR, alineado a la paleta de la consola: menta = encontrado,
            # luz de luna = persona, gris azulado = el resto.
            if is_target or is_recently_found:
                color, thickness, label = (180, 214, 143), 3, f"encontrado: {label_es} {conf:.0%}"
            elif cls_name == "person":
                color, thickness, label = (255, 209, 201), 2, f"{label_es} {conf:.0%}"
            else:
                color, thickness, label = (195, 160, 154), 2, f"{label_es} {conf:.0%}"

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)
            cv2.putText(frame, label, (x1, max(0, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        with self._lock:
            self._last_detections = detections

        if found_now is not None:
            self._register_found_object(found_now)

        return person_present

    def _apply_occupancy(self, person_present: bool) -> None:
        new_state = "occupied" if person_present else "empty"
        if new_state == self._last_occupancy_state:
            return
        self._last_occupancy_state = new_state
        stored = memory.save_event(
            EventIn(
                source=f"camera_{CAMERA_LOCATION}",
                type="motion",
                location=CAMERA_LOCATION,
                metadata={"person_present": person_present},
            )
        )
        agent.apply_event(stored)

    def _apply_door_state(self, gray: np.ndarray) -> None:
        with self._lock:
            baseline = self._door_baseline
        if baseline is None:
            return  # sin calibrar: no se inventa el estado de la puerta

        new_state = door_state_from_diff(mean_gray_diff(gray, baseline))
        if new_state == self._last_door_state:
            return
        self._last_door_state = new_state
        stored = memory.save_event(
            EventIn(
                source=f"camera_{CAMERA_LOCATION}",
                type="door_open" if new_state == "open" else "door_closed",
                location=CAMERA_LOCATION,
            )
        )
        agent.apply_event(stored)

    def _apply_fall_detection(self, frame: np.ndarray, pose) -> None:
        torso = torso_from_pose(frame, pose)
        if torso is None:
            return  # nadie a la vista (o tapado un momento): no cambia nada
        angle, hip_y = torso
        now = time.time()
        if not self._fall_detector.update(now, angle, hip_y):
            return
        if now - self._last_fall_notified_at <= FALL_COOLDOWN_SECONDS:
            return
        self._last_fall_notified_at = now
        agent.report_possible_fall(CAMERA_LOCATION, confidence=None)
        memory.save_event(
            EventIn(
                source=f"camera_{CAMERA_LOCATION}",
                type="possible_fall",
                location=CAMERA_LOCATION,
                metadata={"angle_degrees": round(angle, 1)},
            )
        )

    def _register_found_object(self, found: tuple[str, float]) -> None:
        cls_name, conf = found
        with self._lock:
            if self._search_status != "searching":
                return
            label = self._search_label
            self._search_status = "found"
            self._search_target = None
            self._found_class = cls_name
            self._found_until = time.time() + SEARCH_HOLD_SECONDS
            self._search_result = {
                "object": label,
                "location": CAMERA_LOCATION,
                "confidence": round(conf, 2),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        memory.save_event(
            EventIn(
                source=f"camera_{CAMERA_LOCATION}",
                type="object_detected",
                location=CAMERA_LOCATION,
                confidence=conf,
                metadata={"object": label},
            )
        )


camera = LocalCameraProvider()
