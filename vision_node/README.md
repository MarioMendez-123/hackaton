# Nodo de visión (Raspberry Pi 4 con 4 cámaras)

La Pi solo **ve**: detecta personas, la puerta, caídas y objetos en 4 cámaras
USB, y le manda al servidor de Lumina (en la laptop) **solo lo que cambió**.
Arquitectura completa: `PLAN_MAESTRO.md`, sección 4.

## Instalar (una vez)

```bash
# Raspberry Pi OS Lite 64 bits · ventilador · fuente 5 V/3 A · hub USB con fuente
sudo apt update && sudo apt install -y python3-venv v4l-utils git libgl1
git clone https://github.com/MarioMendez-123/hackaton.git lumina-agent && cd lumina-agent
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt ncnn
yolo export model=yolov8n.pt format=ncnn imgsz=320     # crea yolov8n_ncnn_model/
v4l2-ctl --list-devices                               # qué /dev/video es cada cámara
cp vision_node/cameras.example.json vision_node/cameras.json   # y ajusta "device"
```

- En `cameras.json`, `device` puede ser el número (`0`, `2`, `4`, `6`) o, mejor,
  la ruta fija `/dev/v4l/by-path/...` (no cambia al reconectar).
- `tasks`: `people` (llegó o se fue alguien), `falls` (caídas), `door` (puerta
  por imagen, se calibra desde la consola con "Calibrar puerta").

## Configurar la laptop (el servidor)

En el `.env` de la laptop:

```
LUMINA_HOST=0.0.0.0
DEVICE_TOKEN=una-clave-larga-inventada
```

Luego `python server.py`. Windows pregunta por el firewall: permitir en red privada.

## Correr el nodo

```bash
export LUMINA_SERVER_URL=http://IP-DE-LA-LAPTOP:8000
export DEVICE_TOKEN=la-misma-clave-que-en-la-laptop
export NODE_STREAM_HOST=IP-DE-LA-PI        # o raspberrypi.local
python -m vision_node
```

En la consola de Lumina aparecen las pestañas **Lumina / Cocina / Entrada /
Sala** con el video de cada una.

**Comprobar:**
- `http://IP-DE-LA-PI:8001/health` responde con las cámaras que funcionan.
- `http://IP-DE-LA-LAPTOP:8000/vision/nodes` muestra el nodo "en línea", con
  los cuadros por segundo de cada cámara y la temperatura.

## Ajustes (variables de entorno)

| Variable | Por defecto | Para qué |
|---|---|---|
| `NODE_IMGSZ` | 320 | Tamaño de entrada de YOLO (256 si va lento) |
| `NODE_YOLO_MODEL` | `yolov8n_ncnn_model` si existe | Modelo de YOLO |
| `NODE_MOTION_THRESHOLD` | 4 | Cuánto movimiento dispara el análisis |
| `NODE_IDLE_RECHECK_SECONDS` | 5 | Cada cuánto se revisa una cámara quieta |
| `NODE_PRESENCE_STABLE_SECONDS` | 2 | Cuánto debe sostenerse "hay o no hay alguien" |
| `NODE_ID` | `pi` | Nombre del nodo (si hay más de uno) |
| `NODE_STREAM_PORT` | 8001 | Puerto del video |

## Arranque automático (systemd)

`/etc/systemd/system/lumina-vision.service`:

```
[Unit]
Description=Lumina, nodo de visión
After=network-online.target

[Service]
WorkingDirectory=/home/pi/lumina-agent
EnvironmentFile=/home/pi/lumina-agent/vision_node/node.env
ExecStart=/home/pi/lumina-agent/.venv/bin/python -m vision_node
Restart=always
User=pi

[Install]
WantedBy=multi-user.target
```

`vision_node/node.env` lleva las mismas variables de arriba (sin `export`).
Luego `sudo systemctl enable --now lumina-vision` y
`journalctl -u lumina-vision -f` para ver qué detecta.

**Si va lento o se calienta:**
- `vcgencmd measure_temp` y `vcgencmd get_throttled` (debe decir `0x0`).
- Bajar `NODE_IMGSZ` a 256.
- Quitar `falls` de una cámara.
