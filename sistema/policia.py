"""Elige a qué policía llamar para un punto.

1. El cuadrante MNVCC que contiene el punto, si tiene teléfono (es el celular de la patrulla).
2. Si no: el cuadrante, CAI, estación o subestación con teléfono más cercano, hasta DISTANCIA_MAX_KM.

Los datos son los mismos que dibuja el mapa: mapa/datos/mnvcc_cuadrantes.geojson y la constante D de mapa/index.html.
"""
import json
import math
import re
import unicodedata
from functools import lru_cache

import config

TIPOS_LLAMABLES = ('CAI', 'Estación', 'Subestación')
M_POR_GRADO = 111_320


@lru_cache(maxsize=1)
def unidades():
    html = (config.MAPA / 'index.html').read_text(encoding='utf-8')
    m = re.search(r'^const D=(\[.*\]);$', html, re.M)
    if not m:
        raise RuntimeError('No se encontró "const D=[...]" en mapa/index.html')
    return json.loads(m.group(1))


@lru_cache(maxsize=1)
def cuadrantes():
    g = json.loads((config.DATOS / 'mnvcc_cuadrantes.geojson').read_text(encoding='utf-8'))
    salida = []
    for f in g['features']:
        geo = f['geometry']
        poligonos = geo['coordinates'] if geo['type'] == 'MultiPolygon' else [geo['coordinates']]
        xs = [p[0] for poli in poligonos for anillo in poli for p in anillo]
        ys = [p[1] for poli in poligonos for anillo in poli for p in anillo]
        salida.append({
            'nombre': f['properties']['n'],
            'tel': config.a_e164(f['properties']['t'].split('|')[0]),
            'poligonos': poligonos,
            'bbox': (min(xs), min(ys), max(xs), max(ys)),
        })
    return salida


class _Plano:
    """Proyección local en metros alrededor del punto de la alerta (suficiente para distancias de pocos km)."""

    def __init__(self, lat, lon):
        self.lat, self.lon, self.k = lat, lon, math.cos(math.radians(lat))

    def xy(self, lon, lat):
        return (lon - self.lon) * self.k * M_POR_GRADO, (lat - self.lat) * M_POR_GRADO

    def lonlat(self, x, y):
        return self.lon + x / (self.k * M_POR_GRADO), self.lat + y / M_POR_GRADO

    def dist(self, lon, lat):
        return math.hypot(*self.xy(lon, lat))

    def dist_bbox(self, b):
        dx = max(b[0] - self.lon, 0, self.lon - b[2]) * self.k * M_POR_GRADO
        dy = max(b[1] - self.lat, 0, self.lat - b[3]) * M_POR_GRADO
        return math.hypot(dx, dy)


def _en_anillo(x, y, anillo):
    dentro, j = False, len(anillo) - 1
    for i in range(len(anillo)):
        xi, yi = anillo[i][0], anillo[i][1]
        xj, yj = anillo[j][0], anillo[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            dentro = not dentro
        j = i
    return dentro


def _contiene(c, lon, lat):
    b = c['bbox']
    if not (b[0] <= lon <= b[2] and b[1] <= lat <= b[3]):
        return False
    return any(_en_anillo(lon, lat, poli[0]) and not any(_en_anillo(lon, lat, h) for h in poli[1:])
               for poli in c['poligonos'])


def _borde_mas_cercano(c, plano):
    """Distancia (m) y punto (x, y) del borde del cuadrante más cercanos al origen del plano."""
    mejor = (math.inf, (0.0, 0.0))
    for poli in c['poligonos']:
        for anillo in poli:
            pts = [plano.xy(p[0], p[1]) for p in anillo]
            for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                dx, dy = bx - ax, by - ay
                l2 = dx * dx + dy * dy
                t = 0.0 if l2 == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / l2))
                px, py = ax + t * dx, ay + t * dy
                d = math.hypot(px, py)
                if d < mejor[0]:
                    mejor = (d, (px, py))
    return mejor


def _norm(nombre):
    s = unicodedata.normalize('NFKD', nombre).encode('ascii', 'ignore').decode().lower()
    s = re.sub(r'\b(estacion|subestacion|de|policia|cai)\b', ' ', s)
    return ' '.join(s.split())


def _unidad_base(nombre_cuadrante, lat, lon):
    """CAI/estación a la que pertenece el cuadrante según su nombre ("CAI CHAPINERO CUAD. 005" -> CAI Chapinero)."""
    base = nombre_cuadrante.split(' CUAD')[0]
    clave = _norm(base)
    if not clave:
        return None
    plano = _Plano(lat, lon)
    es_cai = base.upper().startswith('CAI')
    candidatos = [(u['t'] != 'CAI' if es_cai else u['t'] == 'CAI', plano.dist(u['lon'], u['lat']), u)
                  for u in unidades() if u['t'] in TIPOS_LLAMABLES and _norm(u['n']) == clave]
    candidatos = [c for c in candidatos if c[1] < 15_000]
    if not candidatos:
        return None
    u = min(candidatos, key=lambda c: c[:2])[2]
    return {'nombre': u['n'], 'categoria': u['t'], 'tel': config.a_e164((u['tel'] or [''])[0]),
            'lat': u['lat'], 'lon': u['lon']}


def _destino_cuadrante(c, lat, lon, distancia, dentro):
    return {'tipo': 'cuadrante', 'categoria': 'Cuadrante', 'nombre': c['nombre'], 'tel': c['tel'],
            'lat': round(lat, 6), 'lon': round(lon, 6), 'distancia_m': round(distancia), 'dentro': dentro,
            'base': _unidad_base(c['nombre'], lat, lon)}


def mas_cercana(lat, lon, max_km=None):
    """Policía a la que se llama para el punto (lat, lon), o None si no hay ninguna con teléfono cerca.

    En un cuadrante, lat/lon del destino es el punto del cuadrante más cercano a la alerta
    (la propia alerta si está dentro); el mapa lo usa para encontrar el polígono.
    """
    for c in cuadrantes():
        if c['tel'] and _contiene(c, lon, lat):
            return _destino_cuadrante(c, lat, lon, 0, True)

    plano = _Plano(lat, lon)
    mejor_d = (config.DISTANCIA_MAX_KM if max_km is None else max_km) * 1000
    mejor = None
    for c in cuadrantes():
        if not c['tel'] or plano.dist_bbox(c['bbox']) >= mejor_d:
            continue
        d, (x, y) = _borde_mas_cercano(c, plano)
        if d < mejor_d:
            blon, blat = plano.lonlat(x, y)
            mejor_d, mejor = d, _destino_cuadrante(c, blat, blon, d, False)
    for u in unidades():
        tel = config.a_e164((u['tel'] or [''])[0])
        if u['t'] not in TIPOS_LLAMABLES or not tel:
            continue
        d = plano.dist(u['lon'], u['lat'])
        if d < mejor_d:
            mejor_d = d
            mejor = {'tipo': 'unidad', 'categoria': u['t'], 'nombre': u['n'], 'tel': tel, 'direccion': u['d'],
                     'lat': u['lat'], 'lon': u['lon'], 'distancia_m': round(d), 'dentro': False, 'base': None}
    return mejor
