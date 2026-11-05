# Armando

Sistema de alarma que detecta armas de fuego con visión artificial (YOLO) y llama al cuadrante de policía más
cercano con un mensaje de voz: *"Se reportó un arma de fuego en la ubicación: …"*. La alerta se ve en el
[mapa del directorio policial](https://armando-inc.github.io/Armando/Armando/directorio/mapa_directorio.html):
en rojo el punto de la alerta y en amarillo la policía a la que se llamó.

```
cámara → detector.py (YOLO, confirma en varios frames) → alerta.py → Twilio llama
                                                         ↘ registro/alertas.json → mapa (servidor.py)
```

## Estructura

| Ruta | Qué es |
|---|---|
| `Armando/directorio/mapa_directorio.html` | Mapa (Leaflet) publicado en GitHub Pages; 602 unidades embebidas en `D` |
| `Armando/directorio/mnvcc_cuadrantes_web.geojson` | 4.646 cuadrantes MNVCC con el celular de cada patrulla |
| `Armando/directorio/DevMmodel/models/` | Modelos YOLO26n (`rgb_model`, `gray_model`) en `.pt` y `.onnx` |
| `Armando/sistema/detector.py` | Lee la cámara, detecta armas y dispara la alerta |
| `Armando/sistema/alerta.py` | Ubica el punto, elige la policía, llama y registra la alerta (también CLI) |
| `Armando/sistema/policia.py` | Elige a qué policía llamar |
| `Armando/sistema/llamada.py` | Llamada con Twilio y el mensaje de voz |
| `Armando/sistema/servidor.py` | Sirve el mapa en `localhost` con las alertas en vivo |
| `.env.example` | Plantilla de configuración (copiar a `.env`) |

## Instalación

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

En Windows: `.venv\Scripts\pip` y `.venv\Scripts\python` en lugar de `.venv/bin/...`.

## Configuración (`.env`)

Lo mínimo para recibir la llamada de prueba en tu celular:

- `MODO_PRUEBA=true` — todas las llamadas van a `NUMERO_PRUEBA`. **Nunca se llama a la policía en este modo.**
- `NUMERO_PRUEBA` — tu celular, ej. `+573001234567`.
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_NUMERO_ORIGEN` — de la consola de Twilio.
- `UBICACION_NOMBRE` y `UBICACION_LAT`/`UBICACION_LON` (o `UBICACION_DIRECCION`) — dónde está la cámara.

### Twilio

1. Crea la cuenta en <https://www.twilio.com/try-twilio> y copia *Account SID* y *Auth Token* de la consola.
2. Obtén un número de Twilio (*Phone Numbers > Buy a number*); ese es `TWILIO_NUMERO_ORIGEN`.
3. Habilita Colombia en *Voice > Settings > Geo permissions*.
4. Con cuenta de prueba (trial): verifica tu celular en *Phone Numbers > Verified Caller IDs*. La cuenta trial solo
   llama a números verificados y antes del mensaje dice un aviso de Twilio en inglés y pide oprimir una tecla.

### Dirección → coordenadas

Lo más confiable es poner `UBICACION_LAT`/`UBICACION_LON` (clic derecho en Google Maps → copiar coordenadas).
Si solo pones la dirección, se geocodifica con Google (si hay `GOOGLE_MAPS_API_KEY`) o con OpenStreetMap, que
**no entiende bien direcciones colombianas** ("Calle 26 # 68-35" puede caer en otra ciudad): el sistema la marca
como *aproximada* y hay que revisar el punto en el mapa.

## Uso

Mapa en vivo (deja esto corriendo):

```bash
.venv/bin/python Armando/sistema/servidor.py
```

Abre <http://localhost:8000>. Abajo a la izquierda hay un panel para disparar una alerta de prueba escribiendo
nombre y dirección, o con clic derecho sobre el mapa.

Disparar una alerta desde la terminal:

```bash
.venv/bin/python Armando/sistema/alerta.py                      # ubicación del .env
```

```bash
.venv/bin/python Armando/sistema/alerta.py --nombre "Colegio X" --lat 4.6458 --lon -74.0632
```

```bash
.venv/bin/python Armando/sistema/alerta.py --nombre "Colegio X" --direccion "Calle 60 # 7-20" --sin-llamar
```

Imprime la policía elegida, el estado de la llamada y un enlace al mapa con la alerta (`…/mapa_directorio.html#alerta=…`)
que también funciona en GitHub Pages.

Detector con la cámara:

```bash
.venv/bin/python Armando/sistema/detector.py --mostrar
```

```bash
.venv/bin/python Armando/sistema/detector.py --imagen foto.jpg   # probar el modelo con una imagen
```

La alerta se dispara cuando hay arma con confianza ≥ `UMBRAL_CONFIANZA` en `FRAMES_CONFIRMACION` de los últimos
`VENTANA_FRAMES` frames, y no se repite antes de `ENFRIAMIENTO_S` segundos. La foto de la detección queda en
`Armando/sistema/registro/capturas/` y se ve en el mapa local.

## A qué policía se llama

1. Al cuadrante MNVCC que contiene el punto, si tiene teléfono (es el celular de la patrulla).
2. Si no tiene, a la policía con teléfono más cercana (cuadrante, CAI, estación o subestación), hasta
   `DISTANCIA_MAX_KM`.

En el mapa se resalta el cuadrante o la unidad llamada y, si se encuentra por el nombre, el CAI/estación al que
pertenece el cuadrante.

## Modo real

`MODO_PRUEBA=false` hace que el detector llame al teléfono real de la policía. Úsalo solo con autorización de la
estación/MEBOG: los teléfonos de cuadrante cambian con frecuencia y una falsa alarma llega a una patrulla real.
Desde el panel del mapa no se puede llamar en modo real, y la CLI pide escribir `SI` antes de hacerlo.
