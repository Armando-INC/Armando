"""Seguimiento de detecciones entre cuadros: filtro de Kalman + emparejamiento por IoU (estilo SORT).

Cada arma detectada recibe un ID que se mantiene de un cuadro a otro. El filtro de Kalman predice dónde estará la
caja (centro, tamaño y velocidad) y suaviza las que tiemblan; una detección solo queda `confirmed` cuando aparece en
`min_hits` cuadros, y se olvida si desaparece más de `max_age` cuadros. Sirve para descartar detecciones sueltas.

    rastreador = KalmanIoUTracker()
    for frame in video:
        detecciones = [{'bbox': [x1, y1, x2, y2], 'confidence': c, 'class_name': 'Guns'} for x1, y1, x2, y2, c in detector(frame)]
        for t in rastreador.update(detecciones):
            t['track_id'], t['bbox'], t['confirmed']

detector.py lo usa en cada cuadro: para la alerta solo cuentan las armas confirmadas, así que las detecciones sueltas
(una caja que aparece en un lugar distinto cada vez) no la disparan.
"""
import numpy as np


# Intersection over Union
# en caso de detectar muchos objetos
def iou(a, b):
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    x1, y1 = max(ax1, bx1), max(ay1, by1)
    x2, y2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
    return inter / (area_a + area_b - inter + 1e-9)


class Track:
    def __init__(self, track_id, bound_box, confidence, class_name):

        self.id = track_id
        x1, y1, x2, y2 = bound_box 
        #centroide y tamaño
        cx, cy, w, h = (x1+x2)/2, (y1+y2)/2, x2-x1, y2-y1 
        self.x = np.array([cx, cy, w, h, 0, 0, 0, 0], dtype=float)
        self.P = np.eye(8) * 10.0
        self.P[4:, 4:] *= 10

        self.confidence = confidence
        self.class_name = class_name
        self.age = 0
        self.hits = 1
        self.missed = 0

        # proximo estado
    def predict(self):
        dt = 1.0
        F = np.eye(8)
        F[0,4] = F[1,5] = F[2,6] = F[3,7] = dt
        Q = np.eye(8) * 0.05
        Q[4:,4:] *= 0.2
        self.x = F @ self.x
        self.P = F @ self.P @ F.T + Q
        self.age += 1
        self.missed += 1
        return self.bbox()

    # cmbio de estado
    def update(self, bbox, confidence, class_name):
        x1, y1, x2, y2 = bbox
        z = np.array([(x1+x2)/2, (y1+y2)/2, x2-x1, y2-y1], dtype=float)
        H = np.zeros((4,8))
        H[:4,:4] = np.eye(4)
        R = np.eye(4) * 4.0
        innovation = z - H @ self.x
        S = H @ self.P @ H.T + R
        K = self.P @ H.T @ np.linalg.inv(S)
        self.x = self.x + K @ innovation
        self.P = (np.eye(8) - K @ H) @ self.P
        self.confidence = confidence
        self.class_name = class_name
        self.hits += 1
        self.missed = 0

    def bbox(self):
        cx, cy, w, h = self.x[:4]
        w, h = max(2, w), max(2, h)
        return [cx-w/2, cy-h/2, cx+w/2, cy+h/2]


class KalmanIoUTracker:
    def __init__(self, max_age=20, min_hits=2, iou_threshold=0.2):
        self.max_age = max_age
        self.min_hits = min_hits
        self.iou_threshold = iou_threshold
        self.tracks = []
        self.next_id = 1

    def update(self, detections):
        for track in self.tracks:
            track.predict()

        # IoU para evitar duplicados en caso de detectar muchos objetos
        pairs = []
        for ti, track in enumerate(self.tracks):
            for di, det in enumerate(detections):
                score = iou(track.bbox(), det["bbox"])
                if score >= self.iou_threshold:
                    pairs.append((score, ti, di))
        pairs.sort(reverse=True)

        used_t, used_d = set(), set()
        for score, ti, di in pairs:
            if ti in used_t or di in used_d:
                continue
            d = detections[di]
            self.tracks[ti].update(d["bbox"], d["confidence"], d["class_name"])
            used_t.add(ti)
            used_d.add(di)

        for di, det in enumerate(detections):
            if di not in used_d:
                self.tracks.append(Track(self.next_id, det["bbox"], det["confidence"], det["class_name"]))
                self.next_id += 1

        self.tracks = [t for t in self.tracks if t.missed <= self.max_age]
        out = []
        for t in self.tracks:
            if t.missed == 0 and t.hits >= 1:
                out.append({
                    "track_id": t.id, "bbox": t.bbox(), "confidence": t.confidence,
                    "class_name": t.class_name, "confirmed": t.hits >= self.min_hits
                })
        return out
