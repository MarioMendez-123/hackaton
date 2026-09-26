"""Qué decide cada cámara del nodo, sin cámaras ni red (se prueba con imágenes
falsas en test_vision_node.py).

Una Raspberry Pi 4 hace unas 3–5 inferencias de YOLO por segundo en total, así
que cada cámara pregunta primero si vale la pena: solo se analiza si algo se
movió o si pasaron 5 s sin revisarla. Al servidor solo van los CAMBIOS
(alguien llegó o se fue, la puerta, una caída), nunca cada cuadro.

Reutiliza las reglas probadas de backend/vision.py (FallDetector, puerta por
diferencia, nombres en español) para que la laptop y la Pi decidan igual.
"""

import math
import os
from typing import Any

import cv2
import numpy as np

from backend.vision import COCO_LABELS_ES, FallDetector, door_state_from_diff, mean_gray_diff

MOTION_THRESHOLD = float(os.environ.get("NODE_MOTION_THRESHOLD", "4"))  # diferencia media en gris (0–255)
IDLE_RECHECK_SECONDS = float(os.environ.get("NODE_IDLE_RECHECK_SECONDS", "5"))
PRESENCE_STABLE_SECONDS = float(os.environ.get("NODE_PRESENCE_STABLE_SECONDS", "2"))
DOOR_STABLE_SECONDS = 1.0
POSE_AFTER_PERSON_SECONDS = 4.0  # YOLO a veces pierde a alguien acostado: la pose sigue un rato
PERSON_CONFIDENCE = 0.5
FOUND_CONFIDENCE = 0.4
FALL_COOLDOWN_SECONDS = 30
SMALL_SIZE = (160, 120)


def small_gray(frame: np.ndarray) -> np.ndarray:
    """Versión diminuta en gris: barata para medir movimiento y la puerta."""
    return cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), SMALL_SIZE)


class Stable:
    """Un valor que solo cambia si el nuevo se sostiene `seconds` (evita que
    una sombra o un cuadro malo manden eventos de ida y vuelta)."""

    def __init__(self, seconds: float) -> None:
        self.seconds = seconds
        self.value: Any = None
        self._candidate: Any = None
        self._since = 0.0

    def update(self, value: Any, now: float) -> bool:
        """True si el valor confirmado cambió en esta llamada."""
        if value == self.value:
            self._candidate = None
            return False
        if value != self._candidate:
            self._candidate, self._since = value, now
        if now - self._since < self.seconds:
            return False
        self.value, self._candidate = value, None
        return True


class CameraLogic:
    def __init__(self, cam_id: str, zone: str, tasks: list[str], node_id: str = "pi") -> None:
        self.cam_id = cam_id
        self.zone = zone
        self.tasks = set(tasks)
        self.source = f"{node_id}_{cam_id}"
        self.detections: list[dict[str, Any]] = []  # lo último que vio, en español (para "Veo: …")
        self.boxes: list[dict[str, Any]] = []  # con cajas, para dibujar el video
        self._last_small: np.ndarray | None = None
        self._last_inference_at: float | None = None
        self._person_seen_at = -math.inf
        self._presence = Stable(PRESENCE_STABLE_SECONDS)
        self._door = Stable(DOOR_STABLE_SECONDS)
        self._door_baseline: np.ndarray | None = None
        self._calibrate_next = False
        self._fall = FallDetector()
        self._last_fall_at = -math.inf

    # ---- ¿vale la pena correr YOLO? -------------------------------------------

    def needs_inference(self, small: np.ndarray, now: float) -> bool:
        moved = self._last_small is not None and mean_gray_diff(small, self._last_small) >= MOTION_THRESHOLD
        self._last_small = small
        stale = self._last_inference_at is None or now - self._last_inference_at >= IDLE_RECHECK_SECONDS
        return moved or stale

    # ---- personas --------------------------------------------------------------

    def on_detections(self, detections: list[dict[str, Any]], now: float) -> list[dict[str, Any]]:
        """detections: [{"label": nombre COCO, "confidence": 0.9, "box": [x1, y1, x2, y2]}]."""
        self._last_inference_at = now
        self.boxes = detections
        self.detections = [
            {"label": COCO_LABELS_ES.get(d["label"], d["label"]), "confidence": round(d["confidence"], 2)}
            for d in detections
        ]
        person = any(d["label"] == "person" and d["confidence"] >= PERSON_CONFIDENCE for d in detections)
        if person:
            self._person_seen_at = now
        if "people" in self.tasks and self._presence.update(person, now):
            return [self._event("motion", {"person_present": person})]
        return []

    # ---- puerta ------------------------------------------------------------------

    def request_calibration(self) -> None:
        """La siguiente imagen queda como "puerta cerrada"."""
        self._calibrate_next = True

    def door_update(self, small: np.ndarray, now: float) -> list[dict[str, Any]]:
        if "door" not in self.tasks:
            return []
        if self._calibrate_next:
            self._door_baseline = small.copy()
            self._calibrate_next = False
        if self._door_baseline is None:
            return []  # sin calibrar no se inventa el estado de la puerta
        state = door_state_from_diff(mean_gray_diff(small, self._door_baseline))
        if not self._door.update(state, now):
            return []
        return [self._event("door_open" if state == "open" else "door_closed")]

    # ---- caídas --------------------------------------------------------------------

    def wants_pose(self, now: float) -> bool:
        return "falls" in self.tasks and now - self._person_seen_at <= POSE_AFTER_PERSON_SECONDS

    def fall_update(self, torso: tuple[float, float] | None, now: float) -> list[dict[str, Any]]:
        if torso is None:
            return []
        angle, hip_y = torso
        if not self._fall.update(now, angle, hip_y):
            return []
        if now - self._last_fall_at < FALL_COOLDOWN_SECONDS:
            return []
        self._last_fall_at = now
        return [self._event("possible_fall", {"angle_degrees": round(angle, 1)})]

    # ---- búsqueda ----------------------------------------------------------------

    def found(self, detections: list[dict[str, Any]], target: str) -> float | None:
        """Confianza con que ve el objeto buscado (nombre COCO), o None."""
        confidences = [d["confidence"] for d in detections if d["label"] == target and d["confidence"] >= FOUND_CONFIDENCE]
        return max(confidences) if confidences else None

    def _event(self, event_type: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        return {
            "source": self.source,
            "type": event_type,
            "location": self.zone,
            "metadata": {"camera": self.cam_id, **(metadata or {})},
        }
