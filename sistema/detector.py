"""Detector de armas con YOLO (ONNX) sobre una cámara. Al confirmar un arma dispara la alerta.

Las detecciones pasan por el seguimiento (seguimiento.py, Kalman + IoU) y la alerta se dispara cuando hay un arma
confirmada en FRAMES_CONFIRMACION de los últimos VENTANA_FRAMES cuadros. La ubicación y la policía destino se
calculan una vez al arrancar (la cámara es fija), así en el momento de la alerta solo falta llamar.

  python sistema/detector.py --mostrar                 # cámara del .env (CAMARA)
  python sistema/detector.py --imagen foto.jpg         # probar el modelo con una imagen
  python sistema/detector.py --sin-llamar --mostrar    # todo menos la llamada
"""
import argparse
import collections
import os
import sys
import time

import cv2
import numpy as np
import onnxruntime as ort

import alerta
import config
from seguimiento import KalmanIoUTracker

# La ventana de OpenCV usa Qt. En Linux avisa que ignora Wayland y que no encuentra fuentes (OpenCV apunta, al
# importarse, a una carpeta que no trae); no afecta nada, pero así la terminal queda limpia
if sys.platform.startswith('linux'):
    if os.environ.get('XDG_SESSION_TYPE') == 'wayland' and 'QT_QPA_PLATFORM' not in os.environ:
        os.environ['QT_QPA_PLATFORM'], os.environ['XDG_SESSION_TYPE'] = 'xcb', 'x11'
    if os.path.isdir('/usr/share/fonts/truetype/dejavu'):
        os.environ['QT_QPA_FONTDIR'] = '/usr/share/fonts/truetype/dejavu'


class Detector:
    def __init__(self, modelo=None, umbral=None):
        ruta = config.MODELOS / f'{modelo or config.MODELO}_model.onnx'
        self.sesion = ort.InferenceSession(str(ruta), providers=ort.get_available_providers())
        entrada = self.sesion.get_inputs()[0]
        self.nombre, self.canales = entrada.name, entrada.shape[1]
        # exportado con dynamic=True el tamaño viene como texto: se usa 640, el de entrenamiento
        self.alto, self.ancho = (d if isinstance(d, int) else 640 for d in entrada.shape[2:])
        # exportado con end2end (por defecto en YOLO26) la salida es (1, 300, 6) y ya viene sin duplicados
        self.end2end = self.sesion.get_outputs()[0].shape[-1] == 6
        self.umbral = config.UMBRAL_CONFIANZA if umbral is None else umbral

    def __call__(self, frame):
        """Devuelve [(x1, y1, x2, y2, confianza), ...] en píxeles del frame original."""
        h, w = frame.shape[:2]
        r = min(self.ancho / w, self.alto / h)
        nw, nh = round(w * r), round(h * r)
        dx, dy = (self.ancho - nw) // 2, (self.alto - nh) // 2
        img = cv2.resize(frame, (nw, nh))
        if self.canales == 1:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)[..., None]
        else:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        lienzo = np.full((self.alto, self.ancho, self.canales), 114, np.uint8)
        lienzo[dy:dy + nh, dx:dx + nw] = img
        blob = lienzo.transpose(2, 0, 1)[None].astype(np.float32) / 255

        salida = self.sesion.run(None, {self.nombre: blob})[0][0]
        if self.end2end:
            # (300, 6): x1, y1, x2, y2, confianza, clase
            pred = salida[salida[:, 4] >= self.umbral]
            return [(int((x1 - dx) / r), int((y1 - dy) / r), int((x2 - dx) / r), int((y2 - dy) / r), float(c))
                    for x1, y1, x2, y2, c, _ in pred]

        # (4 + clases, 8400): cx, cy, w, h y una confianza por clase; falta quitar duplicados (NMS)
        pred = salida.T
        conf = pred[:, 4:].max(axis=1)
        pred, conf = pred[conf >= self.umbral], conf[conf >= self.umbral]
        if not len(pred):
            return []
        cajas = np.stack([(pred[:, 0] - pred[:, 2] / 2 - dx) / r, (pred[:, 1] - pred[:, 3] / 2 - dy) / r,
                          pred[:, 2] / r, pred[:, 3] / r], axis=1)
        indices = cv2.dnn.NMSBoxes(cajas.tolist(), conf.tolist(), self.umbral, 0.45)
        return [(int(x), int(y), int(x + bw), int(y + bh), float(conf[i]))
                for i in np.array(indices).flatten() for x, y, bw, bh in [cajas[i]]]


def _caja(frame, x1, y1, x2, y2, texto, color):
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
    cv2.putText(frame, texto, (x1, max(y1 - 6, 12)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)


def dibujar(frame, detecciones):
    for x1, y1, x2, y2, conf in detecciones:
        _caja(frame, x1, y1, x2, y2, f'arma {conf:.2f}', (0, 0, 255))
    return frame


def dibujar_seguimiento(frame, seguidas):
    """Cada arma con su ID: roja si el seguimiento ya la confirmó, naranja si todavía no."""
    for s in seguidas:
        x1, y1, x2, y2 = (int(v) for v in s['bbox'])
        _caja(frame, x1, y1, x2, y2, f'arma #{s["track_id"]} {s["confidence"]:.2f}',
              (0, 0, 255) if s['confirmed'] else (0, 165, 255))
    return frame


def probar_imagen(detector, ruta):
    frame = cv2.imread(ruta)
    if frame is None:
        sys.exit(f'No se pudo abrir la imagen {ruta}')
    t = time.time()
    detecciones = detector(frame)
    print(f'{len(detecciones)} arma(s) en {(time.time() - t) * 1000:.0f} ms: {detecciones}')
    salida = ruta.rsplit('.', 1)[0] + '_detecciones.jpg'
    cv2.imwrite(salida, dibujar(frame, detecciones))
    print(f'Resultado: {salida}')


def vigilar(detector, fuente, llamar, mostrar):
    u, destino = alerta.preparar()
    print(f'Cámara en: {u["nombre"]} ({u["lat"]:.5f}, {u["lon"]:.5f}, ubicación {u["precision"]})')
    print(f'Policía a la que se llamará: {destino["nombre"]} · {destino["tel"]}' if destino
          else 'OJO: no hay policía con teléfono cerca de la cámara')
    print('MODO PRUEBA: las llamadas van a NUMERO_PRUEBA' if config.MODO_PRUEBA
          else 'MODO REAL: las alertas llaman a la policía')

    camara = cv2.VideoCapture(int(fuente) if fuente.isdigit() else fuente)
    if not camara.isOpened():
        sys.exit(f'No se pudo abrir la cámara {fuente}')
    es_archivo = not fuente.isdigit() and '://' not in fuente
    rastreador = KalmanIoUTracker()
    ventana = collections.deque(maxlen=config.VENTANA_FRAMES)
    ultima = 0.0
    print(f'Vigilando... alerta con un arma confirmada por el seguimiento en {config.FRAMES_CONFIRMACION} de '
          f'{config.VENTANA_FRAMES} cuadros (confianza ≥ {detector.umbral}). Ctrl+C para salir.')
    try:
        while True:
            ok, frame = camara.read()
            if not ok and es_archivo:
                print('Fin del video.')
                break
            if not ok:
                print('Sin imagen de la cámara, reintentando...')
                time.sleep(1)
                camara.release()
                camara = cv2.VideoCapture(int(fuente) if fuente.isdigit() else fuente)
                continue
            # solo cuentan las armas que el seguimiento confirmó (la misma caja en varios cuadros): una detección
            # suelta, que salta de un lado a otro, no suma para la alerta
            seguidas = rastreador.update([{'bbox': list(d[:4]), 'confidence': d[4], 'class_name': 'arma'}
                                          for d in detector(frame)])
            ventana.append(max((s['confidence'] for s in seguidas if s['confirmed']), default=0.0))
            confirmadas = [c for c in ventana if c > 0]
            if len(confirmadas) >= config.FRAMES_CONFIRMACION and time.time() - ultima >= config.ENFRIAMIENTO_S:
                ultima = time.time()
                ventana.clear()
                config.CAPTURAS.mkdir(parents=True, exist_ok=True)
                captura = time.strftime('%Y%m%d_%H%M%S') + '.jpg'
                cv2.imwrite(str(config.CAPTURAS / captura), dibujar_seguimiento(frame.copy(), seguidas))
                a = alerta.disparar(u, destino, llamar=llamar,
                                    extra={'confianza': round(max(confirmadas), 3), 'captura': captura})
                print(alerta.resumen(a), flush=True)
                if a['llamada'].get('sid'):
                    alerta.seguir_llamada(a)
            if mostrar:
                cv2.imshow('Armando', dibujar_seguimiento(frame, seguidas))
                if cv2.waitKey(1) & 0xFF in (ord('q'), 27):
                    break
    except KeyboardInterrupt:
        pass
    finally:
        camara.release()
        cv2.destroyAllWindows()


def main():
    p = argparse.ArgumentParser(description='Detector de armas de fuego con alerta a la policía.')
    p.add_argument('--camara', default=config.CAMARA, help='índice de webcam o URL RTSP/HTTP (por defecto CAMARA)')
    p.add_argument('--modelo', choices=('rgb', 'gray'), default=config.MODELO)
    p.add_argument('--umbral', type=float, help='confianza mínima (por defecto UMBRAL_CONFIANZA)')
    p.add_argument('--imagen', help='solo detectar en esta imagen y guardar el resultado')
    p.add_argument('--sin-llamar', action='store_true', help='registra la alerta en el mapa pero no llama')
    p.add_argument('--mostrar', action='store_true', help='ventana con el video y las detecciones')
    args = p.parse_args()

    detector = Detector(args.modelo, args.umbral)
    if args.imagen:
        return probar_imagen(detector, args.imagen)
    try:
        vigilar(detector, str(args.camara), not args.sin_llamar, args.mostrar)
    except ValueError as e:
        sys.exit(f'Error: {e}')


if __name__ == '__main__':
    main()
