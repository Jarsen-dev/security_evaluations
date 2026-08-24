# Convenciones del proyecto

Sistema de evaluación de conocimientos para uso industrial interno. Antes de
tocar código, lee estas reglas: varias existen porque romperlas causó un bug
real durante el desarrollo.

---

## Reglas críticas

### 1. Nunca exponer `es_correcta` en endpoints públicos

El formulario `/r/[token]` se sirve **sin autenticación**. Si la respuesta
correcta viaja al navegador, cualquiera la ve abriendo las herramientas de
desarrollo.

- Los schemas públicos viven en `app/schemas/publico.py` y **ninguno** declara
  ese campo. `OpcionPublica` existe precisamente para eso: no reutilices
  `OpcionOut` (del panel) en una ruta pública.
- La respuesta del autoguardado (`PATCH`) tampoco revela si acertó: eso
  convertiría el formulario en un detector de respuestas por prueba y error.
- `es_correcta` se calcula **siempre en el servidor**, comparando contra la
  base de datos. El cliente nunca informa si acertó.

Auditoría rápida:

```bash
# La respuesta real del formulario. Debe dar 0.
curl -s http://localhost:8080/api/publico/<token> | grep -c es_correcta

grep -n es_correcta backend/app/schemas/publico.py   # debe salir vacío
```

`/api/openapi.json` ya no sirve para auditar: en producción no se publica
(ver regla 7). Para revisar el esquema completo, genéralo dentro del
contenedor:

```bash
docker-compose exec backend python -c \
  "import json; from app.main import app; print(json.dumps(app.openapi()))"
```

### 2. Las migraciones deben ser idempotentes

Una migración tiene que poder re-ejecutarse sobre una base parcialmente
migrada sin fallar. Usa `CREATE TABLE/INDEX IF NOT EXISTS` o bloques
condicionales:

```python
op.execute("""
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_ejemplo'
    ) THEN
        ALTER TABLE tabla ADD CONSTRAINT uq_ejemplo UNIQUE (columna);
    END IF;
END $$;
""")
```

Cada migración necesita un `downgrade()` funcional. Prueba la idempotencia
borrando la fila de `alembic_version` y volviendo a correr `alembic upgrade
head`.

### 3. Las opciones se reconcilian por `id`, nunca se reemplazan

`respuestas.opcion_id` apunta a `opciones` con `ON DELETE SET NULL`. Si al
editar un cuestionario borras las opciones y las recreas, **todas las
respuestas históricas pierden qué opción eligió cada persona**, aunque el
texto no haya cambiado. Pasó: una edición dejó 1552 respuestas con
`opcion_id` en NULL y el desglose por opción en ceros.

Ver `_sincronizar_opciones()` y `_sincronizar_preguntas()` en
`app/services/cuestionario_service.py`. El frontend debe enviar de vuelta el
`id` de cada opción existente.

### 4. Las agregaciones van en SQL, no en Python

Nada de cargar todos los intentos a memoria para contarlos. Usa `GROUP BY`,
`FILTER`, `AVG`, `COUNT`. Ver `app/services/estadistica_service.py`.

La única excepción es el pivote de la hoja "Respuestas detalladas" del Excel,
que arma columnas dinámicas: eso es presentación, no agregación.

### 5. El frontend debe funcionar en un contexto NO seguro

El navegador solo considera "seguro" a HTTPS y a `localhost`. Por el dominio
público hay HTTPS y todo existe, pero el sistema **se sigue pudiendo abrir por
la IP de la LAN** (`http://192.168.1.78:8080`), que es la vía de respaldo si el
túnel se cae. Ahí varias APIs del navegador **no existen**, ni siquiera fallan:
son `undefined`.

| API | Por `localhost` | Por `http://192.168.1.x` |
|---|---|---|
| `crypto.randomUUID` | funciona | **undefined** |
| `navigator.clipboard` | funciona | **undefined** |
| `crypto.getRandomValues` | funciona | funciona |
| `localStorage` | funciona | funciona |

Pasó en producción: `crypto.randomUUID()` tumbaba el constructor de
cuestionarios con *"Application error: a client-side exception has occurred"*,
y el desarrollo en `localhost` nunca lo detectó.

Usa siempre los envoltorios de `src/lib/navegador.ts` (`idUnico()`,
`copiarAlPortapapeles()`). **Nunca llames a esas APIs directamente.**

Que ahora el acceso normal sea HTTPS no vuelve opcionales los envoltorios: la
vía de respaldo por IP dejaría de funcionar. Antes de dar por bueno un cambio
en el frontend, pruébalo entrando por la IP de LAN, no por `localhost`:

```
http://<tu-ip>:8080     ←  así se ve en planta
```

### 6. El español es la base; el panel además se traduce

Nada de texto en inglés escrito a mano en la interfaz. La regla sigue viva
para todo lo que no pasa por el diccionario:

- **Los mensajes de error de la API van en español.** Starlette y Pydantic los
  generan en inglés, así que `app/main.py` los traduce con `MENSAJES_HTTP` y
  `MENSAJES_VALIDACION`. Si agregas un validador propio, lanza el `ValueError`
  con el mensaje ya en español: el handler lo conserva tal cual.
- **El formulario público `/r/[token]` va en español.** Lo contesta el personal
  de piso y se imprime en español.

El **panel** sí cambia de idioma (español, inglés y coreano) con el selector
del encabezado. Al escribir un componente del panel:

- Nada de texto suelto en el JSX: todo sale de `t('seccion.clave')`, con
  `useTraduccion()` o `useIdioma()` de `src/lib/i18n`.
- La clave se agrega primero en `es.ts`. `en.ts` y `ko.ts` están tipados como
  `Diccionario = typeof es`, así que `npm run typecheck` falla hasta que se
  traduce en los tres idiomas. Esa es la red de seguridad: no hay forma de
  dejar un idioma a medias sin romper la compilación.
- Los datos capturados no se traducen nunca: nombres de cuestionarios,
  preguntas, observaciones y las etiquetas de área que sirve el backend son
  dato, no interfaz.
- Las fechas y los números se formatean con `Intl` usando el `locale` que
  entrega `useIdioma()`, no con `'es-MX'` fijo.

### 7. El sistema está publicado en internet

Un túnel de Cloudflare sirve el sitio en `https://evaluaciones.chwon.it.com`.
El túnel publica **todo**, no solo el formulario, así que la pantalla de
acceso al panel también es alcanzable desde fuera.

Dos consecuencias al escribir código:

- **La documentación de la API no se publica.** `docs_url` y `openapi_url`
  dependen de `settings.docs_publicas`, que solo es cierto en desarrollo.
- **Un endpoint de administración nuevo tiene que colgar de un prefijo ya
  protegido.** Cloudflare Access filtra por ruta, y las aplicaciones creadas
  cubren `api/auth`, `api/cuestionarios`, `api/preguntas`, `api/estadisticas`,
  `api/metas-area` y `api/wifi`. Un endpoint de admin en un prefijo nuevo
  (`/api/reportes`, digamos) queda fuera de Access sin que nada falle de forma
  visible: solo lo defiende la cookie de sesión. Si agregas uno, cuélgalo de
  un prefijo existente o da de alta la aplicación de Access correspondiente y
  anótala en `SEGURIDAD.md`.

  Los controles ESH estrenaron el prefijo `api/controles`, y el panel las
  rutas `controles` e `inventario`. **Sus aplicaciones de Access todavía están
  pendientes de crear**; queda anotado en `SEGURIDAD.md`.

El límite de tasa distingue dos cuotas (`core/ratelimit.py`): la amplia de
`/api/publico` y una estricta de 5 fallos por 5 minutos en `/api/auth/login`.
En el login **solo cuentan los 401**, para que un admin no se autobloquee.

`SEGURIDAD.md` tiene el detalle: configuración de Access, revisión previa a
repartir el QR, vigilancia y los riesgos que el diseño acepta.

---

## Estilo de código

**Python**

- Type hints completos. Nada de `except: pass`; los errores se manejan o se
  propagan.
- Nombres de dominio en español (`cuestionario`, `intento`, `puntaje`);
  infraestructura genérica en inglés (`get_db`, `settings`, `router`).
- Los servicios lanzan las excepciones de `app/core/errors.py`
  (`ErrorDeNegocio` → 422, `RecursoNoEncontrado` → 404, `ConflictoDeNegocio` →
  409). No importes FastAPI en la capa de servicio.
- La configuración se lee **solo** desde `app/core/config.py`. Ningún módulo
  toca `os.environ` por su cuenta.

**TypeScript**

- Sin `any` salvo justificación en comentario.
- Los colores se definen como tokens en `tailwind.config.ts`. No uses valores
  arbitrarios (`bg-[#123456]`) en los componentes. Las gráficas son la
  excepción: recharts necesita colores reales, y están en
  `components/estadisticas/colores.ts`.
- Sin `console.log` de depuración en el código final.

---

## Arquitectura

```
Navegador → Nginx (8080) → /api/*  → FastAPI (8000) → PostgreSQL
                         → resto   → Next.js (3000)
```

Nginx es el único punto de entrada. El frontend llama a `/api/...` en rutas
relativas, así que comparte origen con la API y la cookie de sesión viaja sola.

**Backend** (`backend/app/`)

| Carpeta | Responsabilidad |
|---|---|
| `api/routes/` | Solo HTTP: validar entrada, llamar al servicio, serializar |
| `services/` | Lógica de negocio. No conoce FastAPI |
| `models/` | SQLAlchemy. Se importan todos en `models/__init__.py` para Alembic |
| `schemas/` | Pydantic. `publico.py` está separado a propósito (ver regla 1) |
| `core/` | Configuración, constantes, catálogos de los controles, seguridad, límite de tasa, errores |

Las exportaciones viven en `services/`: `excel_export.py` y `pptx_export.py`
(reportes de estadísticas), `pdf_export.py` (cuestionario imprimible),
`controles_excel.py` (formatos de los controles ESH) y `exportacion_comun.py`
con lo que comparten: estilos de hoja, la cabecera de descarga y los helpers
de fecha. Todas generan en `BytesIO` y se
devuelven con `StreamingResponse`: nada toca el disco del servidor.

**El PDF imprimible nunca marca la respuesta correcta.** Se le entrega a quien
va a contestar. `pdf_export.py` no debe leer `es_correcta` bajo ninguna
circunstancia (misma lógica que la regla 1).

**Controles ESH** (`api/routes/controles.py`, `services/control_service.py`)

Los formatos de inspección que antes se llenaban en papel. Dos reglas propias:

- Los puntos de la inspección de SQP y el rango de los manómetros viven en
  `core/controles_catalogo.py` y se sirven por la API, igual que las áreas: el
  frontend nunca los tiene escritos a mano.
- La semaforización (verde 125–135 psi, rojo abajo, naranja arriba) **se
  calcula en el servidor**. El frontend repite la regla solo para pintar el
  formulario mientras se teclea; lo que se guarda y lo que sale en el Excel lo
  decide el backend.

**Frontend** (`frontend/src/`)

El grupo de rutas `(panel)` comparte el encabezado con las tres pestañas
(Cuestionarios, Controles e Inventario). Estadísticas ya no es una ruta: es
una sub-pestaña dentro de `/cuestionarios`, y la vista activa viaja en la
query (`?vista=estadisticas`). Controles hace lo mismo con `?control=rayser`.

Los textos del panel salen de `src/lib/i18n` (ver regla 6).
`/r/[token]` queda fuera: layout propio, sin sesión y en **tema claro de alto
contraste**, porque se contesta en celulares bajo la luz de la nave.

---

## Decisiones de diseño

**Los campos de identidad no son preguntas.** Nombre, número de empleado y
área son columnas de `intentos`, no filas de `preguntas`: no se califican,
siempre existen, y permiten agrupar estadísticas por área con índices.

**Las áreas se definen en un solo lugar**, `app/core/constants.py`, y se sirven
por `GET /api/areas`. El frontend nunca las tiene escritas a mano. En la base
se guardan sin acentos (`Almacen`) y se muestran con acento (`Almacén`).

**El puntaje pondera por los puntos de cada pregunta.** Con el valor por
defecto (1 punto) equivale al porcentaje simple de aciertos.

**Solo los intentos finalizados cuentan** para estadísticas y para la regla de
intento único. Los abandonados se reportan aparte.

**Un área sin meta capturada muestra "—", no 0%.** La diferencia entre "no
participaron" y "no sabemos cuántos son" importa.

---

## Trampas conocidas

**`docker-compose` v2.24 corrompe los enteros de YAML sin comillas.**
`UVICORN_WORKERS: 1` llega al contenedor como `%!s(int=1)`. Entrecomilla
siempre los valores numéricos de `environment:`.

**Uvicorn lee las variables con prefijo `UVICORN_`.** `UVICORN_WORKERS` se
aplica aunque no pases `--workers`. Un valor corrupto impide el arranque.

**Las rutas estáticas van declaradas antes que las paramétricas.**
`/cuestionarios/plantilla-excel` debe ir antes de `/cuestionarios/{id}`, o
FastAPI intenta leer `"plantilla-excel"` como UUID.

**`request.cookies.has()` de Next devuelve `true` con valor vacío.** El
middleware exige contenido, no solo presencia.

**El middleware de Next NO valida la firma del JWT** y no debe hacerlo: la
llave vive en el backend. Solo evita el parpadeo de cargar el panel para luego
rebotar. La autorización real la aplica la API en cada endpoint.

**openpyxl no acepta datetimes con zona horaria.** Las columnas son
`TIMESTAMPTZ`; usa `sin_zona()` de `services/exportacion_comun.py`.

**PostgreSQL no indexa las llaves foráneas solo.** Sin
`ix_respuestas_opcion_id`, borrar una opción recorría las 188 mil respuestas
(56 ms por opción, y una edición borra decenas).

**`getUserMedia` no sirve para tomar la foto de evidencia.** Es la misma
trampa de la regla 5 y una más encima: la API no existe por HTTP en la IP de
LAN, y aunque se entre por el dominio, Nginx manda
`Permissions-Policy: camera=()` y el navegador la bloquea. La captura se hace
con `<input type="file" accept="image/*" capture="environment">`, que abre la
cámara del celular sin necesitar contexto seguro, y el reescalado con
`<canvas>`, que tampoco lo necesita. Ver
`components/controles/rayser/CampoFoto.tsx`.

**El límite de tasa es por worker.** Con 4 workers de uvicorn, el tope
efectivo por IP es ~4× el configurado. Es aceptable: el objetivo es contener
abuso, no aplicar una cuota exacta.

---

## Mapa de puertos

| Servicio | Interno | Host | Publicado en producción |
|---|---|---|---|
| Nginx | 80 | 8080 | Sí, el único |
| Frontend | 3000 | 3200 | No |
| Backend | 8000 | 8200 | No |
| PostgreSQL | 5432 | 5442 | No |

Evitar (ocupados por otros proyectos del servidor): 3000, 3001, 8000, 8001,
5432, 5433, 5050, 80, 11434.

---

## Antes de dar por terminado un cambio

```bash
docker compose up -d --build
curl http://localhost:8080/api/health
docker compose logs backend | tail -20      # sin trazas de error
```

Si tocaste endpoints públicos, repite la auditoría de la regla 1.
Si tocaste el modelo de datos, prueba la idempotencia de la migración.
Si tocaste el frontend, **ábrelo por la IP de LAN**, no por localhost: es la
única forma de detectar los fallos de contexto no seguro (regla 5).
