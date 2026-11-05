"""Configuración del sistema de alertas, leída del .env de la raíz del repositorio."""
import os
import re
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parents[1]
MAPA = RAIZ / 'mapa'
DATOS = MAPA / 'datos'
MODELOS = RAIZ / 'modelos'
REGISTRO = Path(__file__).resolve().parent / 'registro'
CAPTURAS = REGISTRO / 'capturas'

load_dotenv(RAIZ / '.env')


def _txt(nombre, defecto=''):
    return (os.getenv(nombre) or defecto).strip()


def _num(nombre, defecto, tipo=float):
    v = _txt(nombre)
    return tipo(v) if v else defecto


def a_e164(numero):
    """Normaliza un teléfono colombiano a +57XXXXXXXXXX. Devuelve '' si no es válido."""
    n = re.sub(r'[^\d+]', '', numero or '')
    if n.startswith('+'):
        return n if 8 <= len(n) <= 16 else ''
    if len(n) == 10:
        return '+57' + n
    if len(n) == 12 and n.startswith('57'):
        return '+' + n
    return ''


# Cualquier valor distinto de false/0/no deja el modo prueba encendido: equivocarse aquí no debe llamar a la policía.
MODO_PRUEBA = _txt('MODO_PRUEBA', 'true').lower() not in ('false', 'falso', '0', 'no')
NUMERO_PRUEBA = a_e164(_txt('NUMERO_PRUEBA'))

TWILIO_ACCOUNT_SID = _txt('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = _txt('TWILIO_AUTH_TOKEN')
TWILIO_NUMERO_ORIGEN = _txt('TWILIO_NUMERO_ORIGEN')
# true: cuenta actualizada, se llama desde TWILIO_NUMERO_ORIGEN con el mensaje de Armando.
# false: cuenta trial, Twilio solo deja usar su plantilla y suena su mensaje genérico en inglés.
TWILIO_CUENTA_PAGA = _txt('TWILIO_CUENTA_PAGA', 'false').lower() in ('true', '1', 'si', 'sí', 'yes')
TWILIO_VOZ = _txt('TWILIO_VOZ', 'Polly.Mia')
REPETICIONES_MENSAJE = _num('REPETICIONES_MENSAJE', 2, int)

UBICACION_NOMBRE = _txt('UBICACION_NOMBRE')
UBICACION_DIRECCION = _txt('UBICACION_DIRECCION')
UBICACION_LAT = _num('UBICACION_LAT', None)
UBICACION_LON = _num('UBICACION_LON', None)
CIUDAD = _txt('CIUDAD')

DISTANCIA_MAX_KM = _num('DISTANCIA_MAX_KM', 20.0)

URL_MAPA = _txt('URL_MAPA', 'https://armando-inc.github.io/Armando/mapa/')
PUERTO = _num('PUERTO', 8000, int)

CAMARA = _txt('CAMARA', '0')
MODELO = _txt('MODELO', 'rgb')
UMBRAL_CONFIANZA = _num('UMBRAL_CONFIANZA', 0.6)
FRAMES_CONFIRMACION = _num('FRAMES_CONFIRMACION', 5, int)
VENTANA_FRAMES = _num('VENTANA_FRAMES', 10, int)
ENFRIAMIENTO_S = _num('ENFRIAMIENTO_S', 120.0)


def twilio_configurado():
    return bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN)
