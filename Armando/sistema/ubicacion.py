"""Convierte la ubicación de la cámara (coordenadas o dirección) en un punto con nombre.

Orden de preferencia: coordenadas exactas > Google Geocoding (si hay GOOGLE_MAPS_API_KEY) > Nominatim (OpenStreetMap).
Nominatim no entiende la nomenclatura colombiana ("Calle 26 # 68-35" puede caer en otra ciudad), por eso su
resultado se marca como 'aproximada'.
"""
import json

import requests

import config

AGENTE = 'Armando-alertas/0.1 (+https://github.com/Armando-INC/Armando)'
CACHE = config.REGISTRO / 'geocache.json'


def _consulta(direccion):
    q = direccion
    if config.CIUDAD and config.CIUDAD.lower() not in q.lower():
        q += ', ' + config.CIUDAD
    if 'colombia' not in q.lower():
        q += ', Colombia'
    return q


def _google(q):
    r = requests.get('https://maps.googleapis.com/maps/api/geocode/json', timeout=10,
                     params={'address': q, 'components': 'country:CO', 'key': config.GOOGLE_MAPS_API_KEY})
    r.raise_for_status()
    d = r.json()
    if d['status'] != 'OK':
        raise LookupError(f'Google no encontró la dirección "{q}" ({d["status"]}: {d.get("error_message", "")})')
    res = d['results'][0]
    loc = res['geometry']['location']
    precision = 'google' if res['geometry']['location_type'] in ('ROOFTOP', 'RANGE_INTERPOLATED') else 'aproximada'
    return loc['lat'], loc['lng'], precision, res['formatted_address']


def _nominatim(q):
    r = requests.get('https://nominatim.openstreetmap.org/search', timeout=10, headers={'User-Agent': AGENTE},
                     params={'q': q, 'format': 'jsonv2', 'limit': 1, 'countrycodes': 'co'})
    r.raise_for_status()
    d = r.json()
    if not d:
        raise LookupError(f'OpenStreetMap no encontró la dirección "{q}". Pon UBICACION_LAT/UBICACION_LON en .env')
    return float(d[0]['lat']), float(d[0]['lon']), 'aproximada', d[0]['display_name']


def _geocodificar(direccion):
    q = _consulta(direccion)
    clave = ('google|' if config.GOOGLE_MAPS_API_KEY else 'osm|') + q
    try:
        cache = json.loads(CACHE.read_text(encoding='utf-8'))
    except (FileNotFoundError, json.JSONDecodeError):
        cache = {}
    if clave not in cache:
        cache[clave] = (_google if config.GOOGLE_MAPS_API_KEY else _nominatim)(q)
        config.REGISTRO.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding='utf-8')
    return cache[clave]


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
