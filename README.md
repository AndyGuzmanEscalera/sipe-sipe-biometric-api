# sipe-sipe-biometric-api

API HTTP **de solo lectura** que consulta un reloj biométrico ZKTeco y devuelve la
información normalizada en JSON.

Este proyecto **no es de RRHH, no es de correspondencia y no conoce funcionarios,
contratos, turnos, atrasos, permisos ni ausencias**. Es un *gateway* independiente
de hardware biométrico que puede reutilizar mañana cualquier otro sistema.

```
Cliente / Backend RRHH
        |
        | HTTPS GET
        v
Biometric Reader API
        |
        | pyzk / TCP 4370
        v
Biométrico
```

---

## 1. Objetivo

`hardware -> lectura -> normalizacion -> filtros -> JSON`

* Leer el dispositivo con `pyzk==0.9` (equipos ZKTeco-compatible).
* Normalizar usuarios y marcaciones a un contrato JSON estable.
* Filtrar por fecha, rango y CI en memoria.
* Pagar con `total / offset / limit / count / records`.
* No escribir nunca en el dispositivo.

---

## 2. Arquitectura del proyecto

```
C:\dev\sipe_sipe_biometric_api
├── app/
│   ├── __init__.py
│   ├── main.py                    # instancia FastAPI, middlewares, manejadores de error
│   ├── config.py                  # configuracion por variables de entorno (pydantic-settings)
│   ├── schemas.py                 # contratos JSON y validacion de filtros
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py              # solo GET: /health /device /users /attendance
│   ├── services/
│   │   ├── __init__.py
│   │   ├── biometric_reader.py    # adaptador pyzk de solo lectura (nucleo reutilizado)
│   │   └── attendance_service.py  # filtro, orden y paginacion
│   ├── security/
│   │   ├── __init__.py
│   │   └── auth.py                # token Bearer con comparacion de tiempo constante
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── errors.py              # errores de dominio -> codigos HTTP
│   │   └── records.py             # normalizacion y record_id SHA-256
│   └── tools/
│       ├── __init__.py
│       └── device_check.py        # diagnostico manual de solo lectura
├── tests/                         # pytest, sin contacto con el dispositivo
├── Dockerfile
├── .dockerignore
├── .gitignore
├── .env.example
├── requirements.txt
├── requirements-dev.txt
├── pytest.ini
└── README.md
```

---

## 3. Requisitos

* Python 3.11 o superior (desarrollado y probado con 3.12).
* Docker (opcional, para ejecutar como servicio).
* Acceso de red al reloj biométrico (puerto TCP `4370`).

Dependencias: `fastapi`, `uvicorn`, `pydantic`, `pydantic-settings`, `python-dotenv`,
`pyzk==0.9`, `pytest`, `httpx`.

---

## 4. Instalacion

```bash
cd C:\dev\sipe_sipe_biometric_api
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
copy .env.example .env        # Windows
```

En Linux/macOS: `cp .env.example .env`.

---

## 5. Variables de entorno

| Variable | Obligatoria | Default | Descripcion |
|---|---|---|---|
| `BIOMETRIC_HOST` | si | `192.168.30.90` | IP o host del reloj |
| `BIOMETRIC_PORT` | si | `4370` | Puerto TCP del protocolo ZKTeco |
| `BIOMETRIC_PASSWORD` | no | `0` | Clave de comunicacion del equipo (numerica) |
| `BIOMETRIC_TIMEOUT` | no | `10` | Timeout de red en segundos (0 < t <= 300) |
| `BIOMETRIC_DEVICE_ID` | si | `alcaldia-central` | Identificador del equipo en las respuestas |
| `BIOMETRIC_TRANSPORT` | no | `auto` | `auto`, `tcp` o `udp` |
| `BIOMETRIC_ENCODING` | no | `UTF-8` | Codificacion de los nombres de usuario |
| `BIOMETRIC_API_TOKEN` | si | (vacio) | Token para `Authorization: Bearer <token>` |
| `ATTENDANCE_DEFAULT_LIMIT` | no | `500` | Registros devueltos si no se pide `limit` |
| `ATTENDANCE_MAX_LIMIT` | no | `5000` | Maximo permitido para `limit` |
| `APP_ENV` | no | `production` | Entorno de ejecucion |
| `LOG_LEVEL` | no | `INFO` | Nivel de log |
| `BIOMETRIC_ENABLE_DOCS` | no | `false` | Publica `/docs` y `/openapi.json` |

El token y la clave del equipo se guardan como `SecretStr`: no aparecen en logs,
en `repr()` ni en las respuestas de error.

---

## 6. Ejecucion local

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Equivalente con Uvicorn directo:

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

---

## 7. Docker

Construccion:

```bash
docker build -t sipe-sipe-biometric-api .
```

Ejecucion (puerto publicado solo en `127.0.0.1`):

```bash
docker run -d \
  --name sipe-sipe-biometric-api \
  --env-file .env \
  -p 127.0.0.1:8200:8000 \
  sipe-sipe-biometric-api
```

Notas:

* El proceso dentro del contenedor escucha en `0.0.0.0:8000`.
* **No** se publica ni se expone el puerto `4370` del biometrico. El contenedor
  se conecta **hacia afuera** a `${BIOMETRIC_HOST}:${BIOMETRIC_PORT}`.
* El contenedor corre como usuario no root (`uid 10001`), con `HEALTHCHECK`
  contra `GET /health`.
* Para detenerlo: `docker stop sipe-sipe-biometric-api`.

---

## 8. Endpoints

Todos los metodos HTTP de escritura (POST, PUT, PATCH, DELETE) estan prohibidos:
la API responde `405 Method Not Allowed`.

| Metodo | Ruta | Token | Descripcion |
|---|---|---|---|
| GET | `/health` | no | Estado del servicio. No contacta el dispositivo. |
| GET | `/device` | si | Informacion disponible del equipo en modo lectura. |
| GET | `/users` | si | Usuarios registrados en el reloj. |
| GET | `/attendance` | si | Marcaciones con filtros y paginacion. |

### `GET /health`

```json
{ "status": "ok", "service": "sipe-sipe-biometric-api", "version": "1.0.0" }
```

### `GET /device`

Devuelve unicamente los valores realmente disponibles; los campos ausentes se
omiten de la respuesta.

```json
{
  "device_id": "alcaldia-central",
  "connected": true,
  "device_name": "uFace802 Plus",
  "serial_number": "SN-0001",
  "firmware_version": "Ver 6.60 Apr 22 2019",
  "platform": "ZMM720_TFT",
  "transport": "TCP"
}
```

### `GET /users`

```json
{
  "device_id": "alcaldia-central",
  "total": 2,
  "users": [
    { "uid": 1, "user_id": "4458643", "name": "JUAN PEREZ" },
    { "uid": 2, "user_id": "4458644", "name": null }
  ]
}
```

* `user_id` siempre es **string**: puede representar CI/documento y no se convierte
  a entero.
* `name` es `null` cuando el dispositivo no tiene nombre para ese usuario.
* Nunca se devuelve `password`, `card` ni plantillas biometricas.

### `GET /attendance`

Filtros opcionales:

| Parametro | Formato | Descripcion |
|---|---|---|
| `date` | `YYYY-MM-DD` | Fecha exacta |
| `from` | `YYYY-MM-DD` | Inicio del rango (exige `to`) |
| `to` | `YYYY-MM-DD` | Fin del rango (exige `from`) |
| `ci` | string | Compara contra `user_id`, en texto |
| `limit` | entero | Maximo `ATTENDANCE_MAX_LIMIT` |
| `offset` | entero | `>= 0`, por defecto `0` |

Respuesta:

```json
{
  "device_id": "alcaldia-central",
  "filters": { "date": null, "from": "2026-11-01", "to": "2026-11-11", "ci": "4458643" },
  "total": 20,
  "offset": 0,
  "limit": 500,
  "count": 20,
  "records": [
    {
      "device_id": "alcaldia-central",
      "uid": 1234,
      "user_id": "4458643",
      "timestamp": "2026-11-11T07:55:20",
      "date": "2026-11-11",
      "time": "07:55:20",
      "status": 0,
      "punch": 1,
      "record_id": "sha256..."
    }
  ]
}
```

* `total`: registros que cumplen los filtros **antes** de paginar.
* `count`: registros efectivamente devueltos en la pagina actual.
* `records`: la pagina actual.

---

## 9. Autenticacion

Todas las rutas salvo `GET /health` exigen:

```
Authorization: Bearer <BIOMETRIC_API_TOKEN>
```

* El token **solo** se acepta en la cabecera `Authorization`. No se acepta por
  query string (`?token=...` responde `401`).
* La comparacion es de tiempo constante (`secrets.compare_digest`).
* El token nunca se escribe en los logs ni se devuelve en los errores.
* Si `BIOMETRIC_API_TOKEN` esta vacio, la API responde `503` en las rutas
  protegidas en vez de quedar abierta.

---

## 10. Errores

| Situacion | Codigo | Cuerpo |
|---|---|---|
| Token ausente o invalido | `401` | `{"detail": "..."}` |
| API sin token configurado | `503` | `{"detail": "..."}` |
| Filtros contradictorios (`date` + `from/to`, `from` sin `to`, `from > to`) | `400` | `{"detail": "..."}` |
| `limit` mayor al maximo configurado | `400` | `{"detail": "..."}` |
| Fecha o parametro con formato invalido, `offset < 0`, `limit < 1` | `422` | validacion de FastAPI |
| Metodo de escritura | `405` | `{"detail": "Method Not Allowed"}` |
| Biométrico inaccesible / rechazo de autenticacion | `502` | `{"detail": "No fue posible conectar con el dispositivo biometrico"}` |
| Tiempo limite agotado | `504` | `{"detail": "El dispositivo biometrico no respondio dentro del tiempo limite configurado"}` |
| Error inesperado | `500` | `{"detail": "Error interno inesperado"}` |

Nunca se devuelve stacktrace, direccion IP, puerto ni clave del dispositivo.

---

## 11. Logs

Se registra: endpoint, `device_id`, filtros aplicados, duracion, registros leidos
del dispositivo, registros despues del filtro y registros devueltos.

No se registra: contrasenas, token de la API ni datos sensibles innecesarios.

---

## 12. Pruebas

```bash
pytest
```

Las pruebas **no necesitan el biometrico**: la capa `pyzk` esta simulada
(`tests/fakes.py` y `unittest.mock` sobre `ReadOnlyZK`). Cubren:

health, token ausente, token incorrecto, token valido, token por query string,
fecha exacta, rango, rango invertido, CI, CI + fecha, CI + rango, `limit`,
`offset`, maximo de `limit`, normalizacion, `record_id` determinista, orden,
conexion fallida, timeout, desconexion garantizada ante excepcion, bloqueo de
comandos de escritura y ausencia de metodos HTTP de escritura.

---

## 13. Diagnostico manual (opcional)

```bash
python -m app.tools.device_check
```

Muestra estado de la conexion, informacion basica del equipo, numero de usuarios
y numero de marcaciones. Es de **solo lectura** y **no se ejecuta automaticamente**.

---

## 14. Limitaciones conocidas de pyzk

* **El dispositivo no permite filtrar remotamente.** `get_attendance()` descarga
  el historico completo. Con ~100.000 registros la descarga puede tardar varios
  minutos. El flujo real es: conectar -> descargar historico -> desconectar ->
  normalizar -> filtrar en memoria -> ordenar -> paginar -> responder.
* **El reloj devuelve hora local sin zona horaria.** Los campos `timestamp`,
  `date` y `time` no llevan offset ni `Z`. Quien consume la API debe saber en que
  zona horaria esta configurado el equipo.
* **`status` y `punch` se devuelven con su valor original.** No se traducen a
  entrada/salida/retorno/descanso: no hay confirmacion institucional ni tecnica
  de esa equivalencia.
* **`uid` no es estable.** pyzk lo documenta como "not really used any more" y
  su valor cambia entre lecturas; por eso **no** forma parte del `record_id`.
* **`user_id` puede venir vacio** en algunos registros; en ese caso pyzk usa el
  `uid` del equipo como identificador.
* El protocolo no autentica al usuario final: la "clave" es la clave de
  comunicacion del equipo (`BIOMETRIC_PASSWORD`).

---

## 15. `record_id`

SHA-256 determinista sobre la tupla estable de la marcacion:

```
device_id | user_id | timestamp | status | punch
```

* La serializacion es estable (`json.dumps` con separadores fijos y
  `ensure_ascii=False`), por lo que la misma marcacion produce **siempre** el
  mismo `record_id`.
* `uid` se excluye a proposito porque no es estable en pyzk (ver limitacion
  anterior). El resto de campos si participan.
* Si el `device_id` cambia, el `record_id` cambia: el identificador es valido
  dentro de un mismo equipo.

---

## 16. Orden

El resultado es determinista y ordenado de forma ascendente por:

1. `timestamp`
2. `user_id`
3. `uid` (solo como desempate)
4. `record_id` (desempate final, garantiza unicidad del orden)

---

## 17. Seguridad

* Token Bearer con comparacion de tiempo constante.
* Politica de **solo lectura** aplicada en el driver: `ReadOnlyZK` intercepta
  `__send_command` y rechaza todo comando que no este en la lista blanca
  (`CMD_CONNECT`, `CMD_AUTH`, `CMD_EXIT`, `CMD_GET_VERSION`, `CMD_OPTIONS_RRQ`,
  `CMD_GET_FREE_SIZES`, `CMD_FREE_DATA`, lecturas de asistencia y de usuarios).
  Quedan bloqueados altas/bajas de usuarios, descarga de plantillas, limpieza de
  asistencia, cambio de configuracion, reinicio, apagado y apertura de puerta.
* El contenedor corre como usuario no root, con `read_only` en el compose de
  despliegue y `cap_drop: ALL`.
* No se expone el puerto `4370` del biometrico.
* `.env` esta en `.gitignore`; no se versionan secretos.

---

## 18. Publicacion futura con Cloudflare Tunnel

Todavia **no** existe el tunel. La intencion es:

```
Internet  ->  Cloudflare Tunnel  ->  http://127.0.0.1:8200  ->  contenedor API
```

Pasos previstos (fuera del alcance de este repositorio):

1. Publicar el contenedor en `127.0.0.1:8200`.
2. Instalar `cloudflared` en el servidor y crear el tunel hacia ese puerto.
3. Publicar el subdominio institucional (por ejemplo `biometric.sipesipe.gob.bo`).
4. Mantener la autenticacion Bearer de esta API como segunda barrera.

El dominio **no** esta hardcodeado en el codigo: solo se documenta aqui.

---

## 19. Repositorios

| Repositorio | Contenido |
|---|---|
| `sipe-sipe-biometric-api` | codigo fuente, desarrollo, tests, Dockerfile, documentacion (este repositorio) |
| `sipe-sipe-biometric-api-deploy` | despliegue/QA/servidor: compose, scripts de operacion, `.env` de produccion |

Este repositorio no tiene remoto configurado hasta que se proporcionen las URLs.
