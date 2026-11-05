"""Dispara una alerta de arma de fuego.

Ubica el punto, elige la policía más cercana, llama con Twilio (en modo prueba, a NUMERO_PRUEBA) y guarda la
alerta en registro/alertas.json para que el mapa la pinte.

  python Armando/sistema/alerta.py                                  # ubicación del .env
  python Armando/sistema/alerta.py --nombre "Colegio X" --direccion "Calle 60 # 7-20"
  python Armando/sistema/alerta.py --lat 4.6458 --lon -74.0632 --sin-llamar --abrir
"""
import argparse
import json
import os
import sys
import threading
import uuid
import webbrowser
from datetime import datetime
from urllib.parse import quote

import requests

import config
import llamada
import policia
import ubicacion

ARCHIVO = config.REGISTRO / 'alertas.json'
_cerrojo = threading.Lock()


def leer():
    try:
        return json.loads(ARCHIVO.read_text(encoding='utf-8'))
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _guardar(alerta):
    """Inserta o reemplaza (por id) la alerta en el registro, conservando las 200 más recientes."""
    with _cerrojo:
        todas = [a for a in leer() if a['id'] != alerta['id']] + [alerta]
        todas.sort(key=lambda a: a['hora'])
        config.REGISTRO.mkdir(parents=True, exist_ok=True)
        tmp = ARCHIVO.with_suffix('.tmp')
        tmp.write_text(json.dumps(todas[-200:], ensure_ascii=False, indent=1), encoding='utf-8')
        os.replace(tmp, ARCHIVO)


def preparar(direccion=None, nombre=None, lat=None, lon=None):
    """Ubicación y policía destino. Sin dirección ni coordenadas usa la ubicación del .env."""
    if not direccion and lat is None:
        direccion, lat, lon = config.UBICACION_DIRECCION, config.UBICACION_LAT, config.UBICACION_LON
        nombre = nombre or config.UBICACION_NOMBRE
    u = ubicacion.resolver(direccion, nombre, lat, lon)
    return u, policia.mas_cercana(u['lat'], u['lon'])


def disparar(u, destino, llamar=True, extra=None):
    a = {
        'id': uuid.uuid4().hex[:10],
        'hora': datetime.now().isoformat(timespec='seconds'),
        'lat': u['lat'], 'lon': u['lon'],
        'ubicacion': u['nombre'], 'direccion': u['direccion'], 'precision': u['precision'],
        'mensaje': llamada.mensaje(u),
        'prueba': config.MODO_PRUEBA,
        'destino': destino,
        **(extra or {}),
    }
    # En modo prueba jamás se usa el teléfono de la policía, aunque falte NUMERO_PRUEBA
    numero = config.NUMERO_PRUEBA if config.MODO_PRUEBA else (destino or {}).get('tel', '')
    if not llamar:
        a['llamada'] = {'estado': 'sin_llamar'}
    elif not numero:
        a['llamada'] = {'estado': 'error', 'detalle': 'Falta NUMERO_PRUEBA en .env' if config.MODO_PRUEBA
                        else 'No hay policía con teléfono cerca'}
    else:
        try:
            sid, estado = llamada.llamar(numero, a['mensaje'])
            a['llamada'] = {'estado': estado, 'sid': sid}
        except RuntimeError as e:
            a['llamada'] = {'estado': 'error', 'detalle': str(e)}
    _guardar(a)
    return a


def seguir_llamada(a, en_segundo_plano=True):
    """Actualiza el estado de la llamada en el registro (sonando, contestada, sin respuesta...)."""
    def actualizar(estado, duracion):
        a['llamada'].update(estado=estado, duracion=duracion)
        _guardar(a)
        print(f'  [{a["id"]}] llamada: {estado}', flush=True)

    args = (a['llamada']['sid'], actualizar)
    if en_segundo_plano:
        threading.Thread(target=llamada.seguir, args=args, daemon=True).start()
    else:
        llamada.seguir(*args)


def enlace(a, base=None):
    """Enlace al mapa con la alerta en el #hash (no viaja al servidor). Funciona también en GitHub Pages."""
    datos = {k: a[k] for k in ('id', 'hora', 'lat', 'lon', 'ubicacion', 'direccion', 'precision', 'prueba', 'destino')}
    datos['llamada'] = {'estado': a['llamada'].get('estado')}
    return (base or config.URL_MAPA) + '#alerta=' + quote(json.dumps(datos, ensure_ascii=False, separators=(',', ':')))


def resumen(a):
    d = a['destino']
    lineas = [
        f'ALERTA {a["id"]} · {a["ubicacion"]} ({a["lat"]:.5f}, {a["lon"]:.5f}, ubicación {a["precision"]})',
        f'Policía más cercana: {d["nombre"]} ({d["categoria"]}) · {d["tel"]} · a {d["distancia_m"]} m' if d
        else f'Policía más cercana: ninguna con teléfono a menos de {config.DISTANCIA_MAX_KM:g} km',
    ]
    if d and d.get('base'):
        lineas.append(f'  Unidad del cuadrante: {d["base"]["nombre"]} · {d["base"]["tel"] or "sin teléfono"}')
    if a['prueba']:
        lineas.append('MODO PRUEBA: la llamada va a NUMERO_PRUEBA, no a la policía')
    lineas.append(f'Mensaje: {a["mensaje"]}')
    ll = a['llamada']
    lineas.append(f'Llamada: {ll["estado"]}' + (f' · {ll["detalle"]}' if ll.get('detalle') else '')
                  + (f' · {ll["sid"]}' if ll.get('sid') else ''))
    if a['precision'] == 'aproximada':
        lineas.append('OJO: la dirección se ubicó de forma APROXIMADA. Revisa el punto en el mapa y, si está mal, '
                      'pon UBICACION_LAT/UBICACION_LON o GOOGLE_MAPS_API_KEY en .env')
    return '\n'.join(lineas)


def main():
    p = argparse.ArgumentParser(description='Dispara una alerta de arma de fuego.')
    p.add_argument('--nombre', help='nombre de la ubicación (lo que dice la llamada)')
    p.add_argument('--direccion', help='dirección, ej. "Calle 60 # 7-20"')
    p.add_argument('--lat', type=float)
    p.add_argument('--lon', type=float)
    p.add_argument('--sin-llamar', action='store_true', help='ubica y registra la alerta pero no llama')
    p.add_argument('--abrir', action='store_true', help='abre el mapa con la alerta en el navegador')
    args = p.parse_args()
    if (args.lat is None) != (args.lon is None):
        p.error('--lat y --lon van juntos')

    try:
        u, destino = preparar(args.direccion, args.nombre, args.lat, args.lon)
    except (ValueError, LookupError, requests.RequestException) as e:
        sys.exit(f'Error: {e}')

    if not config.MODO_PRUEBA and not args.sin_llamar:
        print(f'MODO_PRUEBA=false: se va a llamar a la POLICÍA REAL: '
              f'{destino["nombre"] + " " + destino["tel"] if destino else "(ninguna cerca)"}')
        if input('Escribe SI para continuar: ').strip().upper() != 'SI':
            sys.exit('Cancelado.')

    a = disparar(u, destino, llamar=not args.sin_llamar)
    print(resumen(a))
    url = enlace(a)
    print(f'Mapa: {url}')
    print(f'Mapa en vivo (con servidor.py corriendo): http://localhost:{config.PUERTO}/')
    if args.abrir:
        webbrowser.open(url)
    if a['llamada'].get('sid'):
        seguir_llamada(a, en_segundo_plano=False)


if __name__ == '__main__':
    main()
