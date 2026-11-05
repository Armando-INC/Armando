"""Convierte la ubicación de la cámara (coordenadas o dirección) en un punto con nombre.

Si hay coordenadas se usan tal cual. Si no, la dirección se busca en OpenStreetMap (Nominatim). Nominatim no entiende
la nomenclatura colombiana ("Calle 26 # 68-35" puede caer en otra ciudad): cuando solo encuentra la calle, el barrio
o la ciudad, el resultado se marca como 'aproximada'.
"""
import json

import requests

import config

AGENTE = 'Armando-alertas/0.1 (+https://github.com/Armando-INC/Armando)'
CACHE = config.REGISTRO / 'geocache.json'
# Categorías de Nominatim que no señalan un sitio puntual: una calle, un barrio, una ciudad
GENERICAS = ('highway', 'place', 'boundary')


def _consulta(direccion):
    q = direccion
    if config.CIUDAD and config.CIUDAD.lower() not in q.lower():
        q += ', ' + config.CIUDAD
    if 'colombia' not in q.lower():
        q += ', Colombia'
    return q


def _nominatim(q):
    r = requests.get('https://nominatim.openstreetmap.org/search', timeout=10, headers={'User-Agent': AGENTE},
                     params={'q': q, 'format': 'jsonv2', 'limit': 1, 'countrycodes': 'co'})
    r.raise_for_status()
    d = r.json()
    if not d:
        raise LookupError(f'OpenStreetMap no encontró la dirección "{q}". Pon UBICACION_LAT/UBICACION_LON en .env')
    precision = 'aproximada' if d[0].get('category') in GENERICAS else 'lugar'
    return float(d[0]['lat']), float(d[0]['lon']), precision, d[0]['display_name']


def _geocodificar(direccion):
    q = _consulta(direccion)
    try:
        cache = json.loads(CACHE.read_text(encoding='utf-8'))
    except (FileNotFoundError, json.JSONDecodeError):
        cache = {}
    if q not in cache:
        cache[q] = _nominatim(q)
        config.REGISTRO.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding='utf-8')
    return cache[q]


def resolver(direccion='', nombre='', lat=None, lon=None):
    direccion, nombre = (direccion or '').strip(), (nombre or '').strip()
    if lat is not None and lon is not None:
        precision, encontrado = 'exacta', ''
    elif direccion:
        lat, lon, precision, encontrado = _geocodificar(direccion)
    else:
        raise ValueError('Falta la ubicación: pon UBICACION_DIRECCION o UBICACION_LAT/UBICACION_LON en .env '
                         '(o usa --direccion / --lat --lon)')
    if not (-5 < lat < 14 and -82 < lon < -66):
        raise ValueError(f'Las coordenadas ({lat}, {lon}) no están en Colombia')
    return {'nombre': nombre or direccion or f'{lat:.5f}, {lon:.5f}', 'direccion': direccion,
            'lat': round(lat, 6), 'lon': round(lon, 6), 'precision': precision, 'encontrado': encontrado}
