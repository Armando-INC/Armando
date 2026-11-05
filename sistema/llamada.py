"""Llamada con Twilio que reproduce: "Se reportó un arma de fuego en la ubicación: <nombre>"."""
import json
import re
import time
from functools import lru_cache

from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse

import config

ESTADOS_FINALES = {'completed', 'busy', 'failed', 'no-answer', 'canceled'}
PLANTILLA_TRIAL = 'https://webhooks.twilio.com/v1/Voice/Template/voice_text_to_speech'
# Abreviaturas de dirección que la voz leería letra por letra (solo se cambian si van seguidas de un número)
ABREVIATURAS = {'cra': 'Carrera', 'kra': 'Carrera', 'cr': 'Carrera', 'kr': 'Carrera', 'cll': 'Calle', 'cl': 'Calle',
                'av': 'Avenida', 'ak': 'Avenida Carrera', 'ac': 'Avenida Calle', 'dg': 'Diagonal', 'tv': 'Transversal'}

# Errores frecuentes de Twilio al empezar, con lo que hay que hacer en la consola
PISTAS = {
    20003: 'TWILIO_ACCOUNT_SID o TWILIO_AUTH_TOKEN están mal.',
    21210: 'TWILIO_NUMERO_ORIGEN no es un número de tu cuenta Twilio.',
    21212: 'TWILIO_NUMERO_ORIGEN no es válido (usa formato +1...).',
    21211: 'El número destino no es válido.',
    21215: 'Habilita Colombia en Twilio: Voice > Settings > Geo permissions.',
    21219: 'Cuenta de prueba: verifica tu número en Twilio (Phone Numbers > Verified Caller IDs).',
}


def mensaje(ubicacion):
    lugar = ubicacion['nombre']
    if ubicacion['direccion'] and ubicacion['direccion'] != lugar:
        lugar += ', ' + ubicacion['direccion']
    return f'Se reportó un arma de fuego en la ubicación: {lugar}.'


def para_voz(texto):
    """Ajusta la nomenclatura colombiana para que la voz la lea bien: 'Cra. 7 # 7-20' -> 'Carrera 7 número 7 guion 20'."""
    texto = re.sub(r'\b(' + '|'.join(ABREVIATURAS) + r')\b\.?(?=\s*\d)',
                   lambda m: ABREVIATURAS[m.group(1).lower()], texto, flags=re.I)
    texto = re.sub(r'\s*(#|No\.|N°|Nº)\s*', ' número ', texto)
    texto = re.sub(r'(\d+[A-Za-z]?)\s*-\s*(\d+)', r'\1 guion \2', texto)
    return ' '.join(texto.split())


def twiml(texto):
    r = VoiceResponse()
    r.pause(length=1)
    r.say(para_voz(texto), voice=config.TWILIO_VOZ, language='es-MX', loop=config.REPETICIONES_MENSAJE)
    return str(r)


@lru_cache(maxsize=1)
def _cliente():
    if not config.twilio_configurado():
        raise RuntimeError('Twilio no está configurado: llena TWILIO_ACCOUNT_SID y TWILIO_AUTH_TOKEN en .env')
    return Client(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN)


def llamar(numero, texto):
    """Inicia la llamada y devuelve (sid, estado). Lanza RuntimeError con un mensaje claro si falla."""
    if config.TWILIO_CUENTA_PAGA:
        if not config.TWILIO_NUMERO_ORIGEN:
            raise RuntimeError('Falta TWILIO_NUMERO_ORIGEN en .env')
        datos = {'To': numero, 'From': config.TWILIO_NUMERO_ORIGEN, 'Twiml': twiml(texto)}
    else:
        # La cuenta de prueba ("Try out Voice") solo acepta To + una plantilla de Twilio: no deja poner From ni
        # TwiML propio, así que suena el mensaje genérico de Twilio en vez del nuestro
        datos = {'To': numero, 'Url': PLANTILLA_TRIAL}
    # petición directa: calls.create del SDK exige From aunque la cuenta trial no lo acepte
    r = _cliente().request('POST', f'https://api.twilio.com/2010-04-01/Accounts/{config.TWILIO_ACCOUNT_SID}/Calls.json',
                           data=datos)
    c = json.loads(r.text or '{}')
    if r.status_code >= 400:
        codigo, detalle = c.get('code'), c.get('message', r.text)
        if 'trial accounts' in detalle:
            detalle = 'la cuenta de Twilio sigue en trial: pon TWILIO_CUENTA_PAGA=false o actualiza la cuenta'
        raise RuntimeError(f'Twilio rechazó la llamada ({codigo}): {PISTAS.get(codigo, detalle)}')
    return c['sid'], c['status']


def seguir(sid, al_cambiar, limite_s=180):
    """Consulta la llamada cada 3 s hasta que termine; llama al_cambiar(estado, duracion) en cada cambio."""
    previo, fin = None, time.time() + limite_s
    while time.time() < fin:
        try:
            c = _cliente().calls(sid).fetch()
        except TwilioRestException:
            time.sleep(3)
            continue
        if c.status != previo:
            previo = c.status
            al_cambiar(c.status, c.duration)
        if c.status in ESTADOS_FINALES:
            break
        time.sleep(3)
    return previo
