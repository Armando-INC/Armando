"""Servidor local: sirve el mapa y una API para ver las alertas en vivo.

  python sistema/servidor.py        ->  http://localhost:8000

  GET  /api/alertas   alertas dentro de ENFRIAMIENTO_S (el mapa las consulta cada 3 s y marca la más reciente)
  GET  /api/estado    modo prueba y qué falta configurar
  POST /api/alerta    {"nombre", "direccion"} o {"nombre", "lat", "lon"}, opcional "sin_llamar": true
"""
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import requests

import alerta
import config


def _num(v):
    return None if v in (None, '') else float(v)


class Manejador(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(config.MAPA), **kwargs)

    def _json(self, datos, codigo=200):
        cuerpo = json.dumps(datos, ensure_ascii=False).encode('utf-8')
        self.send_response(codigo)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(cuerpo)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_GET(self):
        ruta = urlparse(self.path).path
        if ruta == '/api/alertas':
            self._json(alerta.activas())
        elif ruta == '/api/estado':
            self._json({
                'modo_prueba': config.MODO_PRUEBA,
                'numero_prueba': config.NUMERO_PRUEBA[-4:] if config.NUMERO_PRUEBA else '',
                'twilio': config.twilio_configurado(),
                'ubicacion_env': config.UBICACION_NOMBRE or config.UBICACION_DIRECCION,
            })
        elif ruta.startswith('/capturas/'):
            archivo = config.CAPTURAS / ruta.rsplit('/', 1)[-1]
            if archivo.suffix != '.jpg' or not archivo.is_file():
                return self._json({'error': 'no existe'}, 404)
            datos = archivo.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', 'image/jpeg')
            self.send_header('Content-Length', str(len(datos)))
            self.end_headers()
            self.wfile.write(datos)
        else:
            super().do_GET()

    def do_POST(self):
        if urlparse(self.path).path != '/api/alerta':
            return self._json({'error': 'no existe'}, 404)
        # Solo JSON y del mismo origen: así otra página abierta en el navegador no puede disparar llamadas
        if self.headers.get('Content-Type', '').split(';')[0].strip() != 'application/json':
            return self._json({'error': 'se espera application/json'}, 415)
        origen = self.headers.get('Origin')
        if origen and urlparse(origen).netloc != self.headers.get('Host'):
            return self._json({'error': 'origen no permitido'}, 403)
        try:
            datos = json.loads(self.rfile.read(int(self.headers.get('Content-Length') or 0)) or b'{}')
            llamar = not datos.get('sin_llamar')
            if llamar and not config.MODO_PRUEBA:
                return self._json({'error': 'Desde el mapa solo se llama en modo prueba (MODO_PRUEBA=true)'}, 403)
            u, destino = alerta.preparar(datos.get('direccion') or None, datos.get('nombre'),
                                         _num(datos.get('lat')), _num(datos.get('lon')))
        except (ValueError, LookupError, requests.RequestException) as e:
            return self._json({'error': str(e)}, 400)
        a = alerta.disparar(u, destino, llamar=llamar)
        print(alerta.resumen(a), flush=True)
        if a['llamada'].get('sid'):
            alerta.seguir_llamada(a)
        self._json(a)

    def log_message(self, formato, *args):
        if not self.path.startswith('/api/alertas'):
            super().log_message(formato, *args)


def main():
    servidor = ThreadingHTTPServer(('127.0.0.1', config.PUERTO), Manejador)
    print(f'Mapa en vivo: http://localhost:{config.PUERTO}/')
    print('MODO PRUEBA: las llamadas van a NUMERO_PRUEBA' if config.MODO_PRUEBA
          else 'MODO REAL: las alertas del detector llaman a la policía')
    if not config.twilio_configurado():
        print('Twilio sin configurar: las alertas se verán en el mapa pero no habrá llamada')
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
