# Especificación de proyecto: Sistema de Evaluación de Conocimientos

> **Nota (agosto 2026).** Este documento es la especificación **original**, y
> se conserva tal cual como registro de por qué el sistema quedó como quedó.
> Desde entonces el proyecto se convirtió en el **Sistema ESH** del
> departamento de seguridad: además de las evaluaciones, ahora captura los
> controles de inspección (Rayser e inspección de SQP, con más pestañas por
> habilitar), tiene una sección de inventario y el panel se puede leer en
> español, inglés y coreano. Lo que está descrito aquí sigue vigente para la
> parte de cuestionarios y estadísticas; lo nuevo está documentado en
> `README.md`, `CLAUDE.md` y `SEGURIDAD.md`.

Vas a construir desde cero un sistema web de evaluación de conocimientos (estilo Google Forms) para uso industrial interno, alojado en un servidor local de planta. Este repositorio es completamente independiente de cualquier otro proyecto del servidor y debe correr en puertos propios sin colisionar.

Lee esta especificación completa antes de escribir código. Al final hay un plan de fases: **implementa una fase a la vez y espera confirmación antes de pasar a la siguiente.**

---

## 1. Contexto operativo

- **Escala:** ~500 empleados respondiendo cuestionarios. Pico realista: un turno completo (~150 personas) contestando en la misma ventana de 30–60 minutos.
- **Red:** LAN industrial. Los operadores acceden desde celulares (escaneando QR) o desde PCs de escritorio (liga directa). La cobertura WiFi de planta es irregular, así que la app debe tolerar pérdidas de conexión.
- **Usuarios:** un solo administrador con usuario y contraseña. Los que responden cuestionarios **no tienen cuenta** — acceden por liga pública sin login.
- **Servidor:** Linux con Docker + Docker Compose ya instalados.

---

## 2. Stack obligatorio

| Capa | Tecnología |
|---|---|
| Backend | Python 3.11+, FastAPI, SQLAlchemy 2.x **async**, Pydantic v2 |
| Migraciones | Alembic |
| Base de datos | PostgreSQL 16 |
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind CSS |
| Contenedores | Docker + Docker Compose |
| Reverse proxy | Nginx (contenedor) |

No introduzcas Redis, Celery, ni colas de mensajes. A esta escala es sobre-ingeniería.

**Librerías específicas permitidas:**
- Backend: `asyncpg`, `alembic`, `python-jose[cryptography]` o `pyjwt`, `passlib[bcrypt]`, `openpyxl`, `python-pptx`, `python-multipart`
- Frontend: `@dnd-kit/core` + `@dnd-kit/sortable` (reordenar preguntas), `qrcode` (generar QR en cliente), `recharts` (gráficas), `zod` (validación de formularios)

---

## 3. Aislamiento de puertos

Este servidor ya hospeda otros proyectos. **Todos los puertos y nombres de recursos deben ser configurables por `.env` y no deben chocar.**

Valores por defecto a usar:

```
FRONTEND_PORT=3200
BACKEND_PORT=8200
POSTGRES_PORT=5442
NGINX_PORT=8080
```

Requisitos duros:
- El proyecto Docker Compose debe declarar un `name:` propio (ej. `evaluaciones`) para no colisionar con volúmenes o redes existentes.
- Volumen de Postgres con nombre explícito y único (ej. `evaluaciones_pgdata`).
- Red Docker propia (ej. `evaluaciones_net`), **no** usar la red default compartida.
- Antes de levantar, verifica con `ss -tulpn` qué puertos están ocupados y avísame si alguno de los defaults ya está en uso.

---

## 4. Modelo de datos

### Decisión de diseño importante

Las tres "preguntas fijas" (**Nombre**, **Número de empleado**, **Área**) **NO se modelan como preguntas** en la tabla `preguntas`. Son campos de identidad del respondiente y van como columnas en la tabla `intentos`. Razón: no son calificables, siempre existen, y necesitas agrupar estadísticas por `area` con índices eficientes. En el frontend se renderizan como un bloque fijo al inicio del formulario.

### Tablas

**`admin_users`**
```
id                UUID PK
username          VARCHAR(50) UNIQUE NOT NULL
password_hash     VARCHAR(255) NOT NULL
created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
last_login_at     TIMESTAMPTZ NULL
```

**`cuestionarios`**
```
id                UUID PK
nombre            VARCHAR(200) NOT NULL
descripcion       TEXT NULL
token_publico     VARCHAR(32) UNIQUE NOT NULL   -- token URL-safe aleatorio, NO el UUID
activo            BOOLEAN NOT NULL DEFAULT true  -- si false, la liga pública rechaza respuestas
permitir_multiples_intentos BOOLEAN NOT NULL DEFAULT false
created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
```

**`preguntas`**
```
id                UUID PK
cuestionario_id   UUID FK -> cuestionarios(id) ON DELETE CASCADE
orden             INTEGER NOT NULL
texto             TEXT NOT NULL
puntos            INTEGER NOT NULL DEFAULT 1
created_at        TIMESTAMPTZ NOT NULL DEFAULT now()

UNIQUE (cuestionario_id, orden)  -- deferrable, para permitir reordenar en batch
INDEX (cuestionario_id)
```

**`opciones`**
```
id                UUID PK
pregunta_id       UUID FK -> preguntas(id) ON DELETE CASCADE
orden             INTEGER NOT NULL
texto             TEXT NOT NULL
es_correcta       BOOLEAN NOT NULL DEFAULT false

INDEX (pregunta_id)
```
Regla de negocio: cada pregunta debe tener **exactamente una** opción con `es_correcta = true` y **mínimo 2 opciones**. Valídalo en el servicio antes de permitir publicar el cuestionario.

**`intentos`**
```
id                UUID PK
cuestionario_id   UUID FK -> cuestionarios(id) ON DELETE CASCADE
nombre            VARCHAR(150) NOT NULL
numero_empleado   VARCHAR(30) NOT NULL
area              VARCHAR(30) NOT NULL   -- ver enum abajo
iniciado_at       TIMESTAMPTZ NOT NULL DEFAULT now()
finalizado_at     TIMESTAMPTZ NULL       -- NULL = intento en progreso / abandonado
total_preguntas   INTEGER NOT NULL DEFAULT 0
correctas         INTEGER NOT NULL DEFAULT 0
puntaje           NUMERIC(5,2) NULL      -- porcentaje 0.00–100.00
ip_origen         INET NULL
user_agent        TEXT NULL

INDEX (cuestionario_id, area)
INDEX (cuestionario_id, finalizado_at)
INDEX (numero_empleado)
```

**`respuestas`**
```
id                UUID PK
intento_id        UUID FK -> intentos(id) ON DELETE CASCADE
pregunta_id       UUID FK -> preguntas(id) ON DELETE CASCADE
opcion_id         UUID FK -> opciones(id) NULL
es_correcta       BOOLEAN NOT NULL DEFAULT false
respondido_at     TIMESTAMPTZ NOT NULL DEFAULT now()

UNIQUE (intento_id, pregunta_id)   -- upsert al autoguardar
INDEX (pregunta_id, es_correcta)   -- para estadística "preguntas más falladas"
```

### Enum de áreas

Define las áreas en **un solo lugar** del backend (`app/core/constants.py`) y expónlas por endpoint `GET /api/areas` para que el frontend nunca las tenga hardcodeadas:

```
Ensamble, EPS, Moldes, Mantenimiento, Embarques, Calidad, Almacen, Oficinas
```

Guarda en BD el valor sin acentos (`Almacen`) y muestra la etiqueta con acento (`Almacén`) en la UI mediante un mapa de display.

### Regla de intento único

Si `permitir_multiples_intentos = false`, un `numero_empleado` no puede tener dos intentos **finalizados** del mismo cuestionario. Impleméntalo con un índice único parcial:

```sql
CREATE UNIQUE INDEX uq_intento_unico
ON intentos (cuestionario_id, numero_empleado)
WHERE finalizado_at IS NOT NULL;
```

Este índice debe poder crearse y borrarse dinámicamente según la bandera, o mejor: créalo siempre y valida la bandera en capa de servicio antes del insert, devolviendo un 409 con mensaje claro en español.

---

## 5. Migraciones Alembic

**Regla obligatoria:** todas las migraciones deben ser idempotentes. Usa bloques condicionales de PostgreSQL para que una migración pueda re-ejecutarse sobre una base parcialmente migrada sin explotar:

```python
op.execute("""
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'cuestionarios' AND column_name = 'activo'
    ) THEN
        ALTER TABLE cuestionarios ADD COLUMN activo BOOLEAN NOT NULL DEFAULT true;
    END IF;
END $$;
""")
```

Aplica el mismo patrón para índices (`IF NOT EXISTS`), constraints y tipos. Cada migración debe tener `downgrade()` funcional.

---

## 6. Autenticación

**Admin:**
- Login por `username` + `password`, hash con bcrypt (`passlib`).
- Emite JWT firmado con `SECRET_KEY` de `.env`, expiración 12 horas.
- Guarda el token en cookie `httpOnly`, `SameSite=Lax`, `Secure` solo si hay HTTPS (configurable por env, porque en LAN puede ser HTTP).
- Endpoint `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`.
- **No hay registro público.** El usuario admin se crea con un comando CLI: `python -m app.cli create-admin --username X`, que pide la contraseña por stdin (no la aceptes como argumento, queda en el historial de bash).

**Acceso público a cuestionarios:**
- Sin autenticación. La única credencial es el `token_publico` en la URL.
- El token debe ser criptográficamente aleatorio (`secrets.token_urlsafe(24)`), no secuencial ni derivado del ID.
- Rate limiting en endpoints públicos: máximo 30 requests/minuto por IP. Impleméntalo con un middleware simple en memoria (dict con ventana deslizante); no metas Redis.
- Los endpoints públicos **nunca** deben exponer `es_correcta` de las opciones. Serializa con un schema Pydantic distinto (`OpcionPublica`) que omita ese campo. Esto es crítico: si lo expones, cualquiera abre DevTools y ve las respuestas.

---

## 7. Endpoints de la API

Prefijo `/api`. Todos los mensajes de error en español.

### Auth
```
POST   /api/auth/login
POST   /api/auth/logout
GET    /api/auth/me
```

### Catálogos
```
GET    /api/areas                          -> lista de áreas {value, label}
```

### Cuestionarios (requieren admin)
```
GET    /api/cuestionarios                  -> lista con conteo de intentos
POST   /api/cuestionarios                  -> crea con nombre + preguntas
GET    /api/cuestionarios/{id}             -> detalle completo con preguntas y opciones
PUT    /api/cuestionarios/{id}             -> actualiza nombre/descripcion/activo
DELETE /api/cuestionarios/{id}             -> borra (cascade). Pide confirmación en UI.
POST   /api/cuestionarios/{id}/preguntas   -> agrega pregunta
PUT    /api/preguntas/{id}                 -> actualiza texto/opciones/correcta
DELETE /api/preguntas/{id}
PUT    /api/cuestionarios/{id}/preguntas/orden  -> reordena en batch [{id, orden}]
POST   /api/cuestionarios/{id}/duplicar    -> clona el cuestionario sin respuestas
POST   /api/cuestionarios/importar-excel   -> multipart, ver sección 9
GET    /api/cuestionarios/plantilla-excel  -> descarga la plantilla vacía
```

### Público (sin auth)
```
GET    /api/publico/{token}                -> metadata + preguntas SIN respuestas correctas
POST   /api/publico/{token}/intento        -> {nombre, numero_empleado, area} -> devuelve intento_id
PATCH  /api/publico/intento/{intento_id}   -> {pregunta_id, opcion_id} autoguardado
POST   /api/publico/intento/{intento_id}/finalizar -> calcula puntaje, devuelve resultado
```

**Autoguardado:** el `PATCH` hace upsert en `respuestas` (`ON CONFLICT (intento_id, pregunta_id) DO UPDATE`). Calcula `es_correcta` en el servidor comparando contra `opciones.es_correcta` — nunca confíes en el cliente. La respuesta del PATCH **no** debe revelar si acertó.

### Estadísticas (requieren admin)
```
GET /api/estadisticas/resumen?cuestionario_id=&area=&desde=&hasta=
GET /api/estadisticas/por-area?cuestionario_id=
GET /api/estadisticas/por-pregunta?cuestionario_id=
GET /api/estadisticas/distribucion?cuestionario_id=
GET /api/estadisticas/linea-tiempo?cuestionario_id=
GET /api/estadisticas/intentos?cuestionario_id=&area=&page=&size=   -> tabla paginada
GET /api/estadisticas/exportar/excel?cuestionario_id=
GET /api/estadisticas/exportar/powerpoint?cuestionario_id=
```

Todas las agregaciones se hacen en SQL (`GROUP BY`, `FILTER`, `AVG`, `COUNT`), no en Python cargando todos los registros a memoria.

---

## 8. Frontend

### Rutas

```
/login                          Login del admin
/                               Redirige a /cuestionarios si hay sesión
/cuestionarios                  Pestaña 1
/estadisticas                   Pestaña 2
/r/[token]                      Formulario público (mobile-first)
/r/[token]/gracias              Pantalla de confirmación post-envío
```

Las rutas `/cuestionarios` y `/estadisticas` comparten un layout con las **dos pestañas** en el header. La ruta `/r/[token]` tiene layout propio sin nada del panel admin.

### Pestaña "Cuestionarios"

- Botón primario **"Nuevo cuestionario"** arriba a la derecha → abre modal.
- **Modal de creación**, en dos pasos:
  1. **Paso 1:** campo obligatorio de nombre del cuestionario + descripción opcional. Botón "Continuar" deshabilitado hasta que haya nombre.
  2. **Paso 2:** constructor de preguntas.
     - Bloque superior **fijo y no editable** mostrando los 3 campos que siempre se piden: Nombre, Número de empleado, Área (con las 8 opciones). Muéstralo con estilo atenuado y una etiqueta tipo "Campos fijos — siempre se solicitan".
     - Debajo, lista de preguntas creadas por el usuario. Cada tarjeta de pregunta tiene: input de texto de la pregunta, lista de opciones (input de texto por opción + radio para marcar cuál es la correcta + botón eliminar opción), botón "Agregar opción", botón eliminar pregunta, y handle de arrastre para reordenar (`@dnd-kit`).
     - Botón **"Agregar pregunta"** al final.
     - Botón **"Importar desde Excel"** que abre el selector de archivo. Al importar, las preguntas se **agregan** a las existentes, no reemplazan.
     - Validación en cliente antes de guardar: cada pregunta necesita texto, mínimo 2 opciones con texto, y exactamente una marcada como correcta. Muestra los errores inline, no en un alert.
- **Grid de tarjetas** de cuestionarios existentes. Cada tarjeta muestra:
  - Nombre del cuestionario
  - Número de preguntas y número de respuestas recibidas
  - Badge de estado (Activo / Inactivo)
  - Botón **Editar** → abre el mismo modal en modo edición
  - Botón **QR** → modal con el QR generado en cliente, la URL en texto plano, botón "Descargar PNG" y botón "Copiar liga"
  - Botón **Liga escritorio** → copia la URL al portapapeles y muestra un toast de confirmación
  - Menú de tres puntos con: Duplicar, Activar/Desactivar, Eliminar

**Gotcha crítico del QR:** la URL codificada en el QR **no puede ser `localhost` ni `127.0.0.1`**, o el celular no podrá abrirla. Debe usar la IP o hostname del servidor en la LAN. Toma la base URL de la variable de entorno `NEXT_PUBLIC_BASE_URL` (ej. `http://192.168.1.50:8080`) y valida al arrancar que no contenga `localhost`; si lo contiene, muestra una advertencia visible en el modal del QR indicando que la liga no funcionará desde celulares.

### Formulario público `/r/[token]`

- **Mobile-first.** Los operadores lo van a contestar en celulares posiblemente con guantes. Targets táctiles grandes (mínimo 48px de alto), tipografía generosa, mucho contraste, una pregunta claramente separada de la siguiente.
- Primero pide los 3 campos fijos. El campo Área es un `<select>` con las 8 opciones. Botón "Comenzar" crea el intento y guarda el `intento_id` en `localStorage` con clave `intento_{token}`.
- Después muestra las preguntas. **Autoguarda cada respuesta** con el `PATCH` en cuanto el usuario selecciona una opción. Indicador visual sutil de "Guardado".
- **Tolerancia a fallos de red:** si un `PATCH` falla, encola la respuesta en `localStorage` y reintenta con backoff exponencial. Muestra un banner discreto "Sin conexión — se guardará automáticamente" cuando haya reintentos pendientes. Bloquea el botón "Finalizar" mientras haya cola pendiente.
- Si el usuario recarga la página, recupera el `intento_id` de `localStorage` y restaura sus respuestas ya guardadas desde el servidor.
- Barra de progreso "Pregunta X de Y".
- Botón **"Finalizar"** solo habilitado cuando todas las preguntas tienen respuesta. Pide confirmación.
- Al finalizar, redirige a `/r/[token]/gracias` mostrando el puntaje obtenido y limpia el `localStorage`.
- Si el cuestionario está inactivo o el token no existe, muestra una pantalla de error clara sin filtrar información.

### Pestaña "Estadísticas"

Selector de cuestionario arriba (dropdown), más filtros de área y rango de fechas.

**Tarjetas KPI (fila superior):**
- Total de respuestas recibidas
- Nivel de participación (% sobre la meta configurable de headcount — ver nota abajo)
- Calificación promedio general
- Tasa de aprobación (% que superó el umbral configurable, default 70%)

**Gráficas (recharts):**
1. **Participación por área** — barras: respuestas recibidas vs meta por área
2. **Calificación promedio por área** — barras horizontales ordenadas de mayor a menor
3. **Distribución de calificaciones** — histograma por rangos (0-59, 60-69, 70-79, 80-89, 90-100)
4. **Preguntas con mayor índice de error** — barras horizontales, top 10, con el % de respuestas incorrectas. *Esta es la gráfica más accionable del dashboard: señala qué temas necesitan recapacitación o qué preguntas están mal redactadas.*
5. **Respuestas por día** — línea de tiempo

**Tabla de intentos** paginada al final: Nombre, Núm. empleado, Área, Fecha, Puntaje, con ordenamiento por columna.

**Configuración de metas:** agrega una tabla `metas_area (area VARCHAR PK, headcount INTEGER)` y una pantalla simple para capturar cuántas personas hay por área. Sin esto el "nivel de participación" no tiene denominador. Si no hay meta capturada, muestra el conteo absoluto y oculta el porcentaje.

**Dos botones de exportación** arriba a la derecha: "Descargar Excel" y "Descargar PowerPoint".

### Diseño visual

Tema oscuro, consistente y sobrio — es una herramienta interna de uso frecuente, no una landing page. Define los tokens de color en `tailwind.config.ts` (no uses clases arbitrarias sueltas por todo el código). Componentes reutilizables en `components/ui/`: `Button`, `Input`, `Select`, `Modal`, `Card`, `Badge`, `Toast`, `Table`.

**Excepción importante:** el formulario público `/r/[token]` debe ser **tema claro y alto contraste**. Se va a contestar en celulares bajo luz de nave industrial, donde el tema oscuro se lee mal.

---

## 9. Importación desde Excel

### Formato de la plantilla

Una sola hoja llamada `Preguntas`:

| Pregunta | Opcion 1 | Opcion 2 | Opcion 3 | Opcion 4 | Opcion 5 | Respuesta Correcta |
|---|---|---|---|---|---|---|
| ¿Cuál es el EPP obligatorio en el área de moldes? | Casco | Guantes térmicos | Botas dieléctricas | Todas las anteriores | | 4 |

Reglas del parser:
- Columnas `Opcion 3`, `Opcion 4`, `Opcion 5` son opcionales; celdas vacías se ignoran.
- `Respuesta Correcta` acepta el **número de opción** (1–5) o el **texto exacto** de la opción. Normaliza espacios y mayúsculas al comparar texto.
- Fila con `Pregunta` vacía → se salta silenciosamente (permite filas separadoras).
- Máximo 200 preguntas por archivo.

### Manejo de errores

**No falles todo el archivo por una fila mala.** Devuelve un reporte estructurado:

```json
{
  "importadas": 18,
  "errores": [
    {"fila": 7, "mensaje": "Solo tiene una opción; se requieren mínimo 2"},
    {"fila": 12, "mensaje": "La respuesta correcta '6' no corresponde a ninguna opción"}
  ]
}
```

El frontend muestra ese reporte en el modal: las válidas se agregan al constructor y los errores se listan con el número de fila para que el usuario corrija su Excel. Usa `openpyxl` en modo `read_only=True`.

También implementa `GET /api/cuestionarios/plantilla-excel` que genera y descarga la plantilla con los encabezados correctos, una fila de ejemplo y una segunda hoja de instrucciones.

---

## 10. Exportación

### Excel (`openpyxl`)

Un archivo con cuatro hojas:

1. **Resumen** — nombre del cuestionario, fecha de generación, KPIs generales, umbral de aprobación usado.
2. **Respuestas detalladas** — una fila por intento: Nombre, Núm. empleado, Área, Fecha inicio, Fecha fin, Duración, Correctas, Total, Puntaje %, y **una columna por pregunta** con la opción elegida. Congela la primera fila y la primera columna, activa autofiltro.
3. **Por área** — agregados: intentos, promedio, mínimo, máximo, aprobados, % aprobación, participación vs meta.
4. **Por pregunta** — texto de la pregunta, % de acierto, % de error, y el desglose de cuántos eligieron cada opción. Aplica formato condicional (escala de color) sobre el % de acierto.

Nombre del archivo: `evaluacion_{nombre_slug}_{YYYYMMDD}.xlsx`

### PowerPoint (`python-pptx`)

Presentación 16:9 lista para presentar a gerencia:

1. **Portada** — nombre del cuestionario, periodo, fecha de generación
2. **Resumen ejecutivo** — 4 KPIs en cajas grandes
3. **Participación por área** — gráfica de barras nativa
4. **Calificación promedio por área** — gráfica de barras nativa
5. **Distribución de calificaciones** — gráfica de columnas nativa
6. **Top 10 preguntas con mayor error** — tabla o barras horizontales
7. **Conclusiones** — slide con bullets generados por regla: áreas por debajo del promedio general, áreas con participación menor al 80% de su meta, y las 3 preguntas con mayor índice de error.

Usa **gráficas nativas de python-pptx** (`chart_data` + `add_chart`), no imágenes de matplotlib. Las nativas quedan editables en PowerPoint, que es lo que va a querer quien presente.

Nombre del archivo: `evaluacion_{nombre_slug}_{YYYYMMDD}.pptx`

Ambas exportaciones deben generarse en memoria (`BytesIO`) y devolverse con `StreamingResponse` y el `Content-Disposition` correcto. No escribas archivos temporales en disco.

---

## 11. Estructura del repositorio

```
.
├── docker-compose.yml
├── docker-compose.dev.yml
├── .env.example
├── .gitignore
├── README.md
├── CLAUDE.md
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   └── app/
│       ├── main.py
│       ├── cli.py
│       ├── core/
│       │   ├── config.py          # Pydantic Settings desde .env
│       │   ├── constants.py       # AREAS
│       │   ├── security.py        # hashing, JWT
│       │   └── ratelimit.py
│       ├── db/
│       │   ├── base.py
│       │   └── session.py         # async engine + session factory
│       ├── models/
│       ├── schemas/
│       ├── api/
│       │   ├── deps.py
│       │   └── routes/
│       │       ├── auth.py
│       │       ├── cuestionarios.py
│       │       ├── publico.py
│       │       ├── estadisticas.py
│       │       └── exportacion.py
│       └── services/
│           ├── cuestionario_service.py
│           ├── intento_service.py
│           ├── estadistica_service.py
│           ├── excel_import.py
│           ├── excel_export.py
│           └── pptx_export.py
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── tailwind.config.ts
│   └── src/
│       ├── app/
│       │   ├── layout.tsx
│       │   ├── login/page.tsx
│       │   ├── (panel)/
│       │   │   ├── layout.tsx           # header con las 2 pestañas
│       │   │   ├── cuestionarios/page.tsx
│       │   │   └── estadisticas/page.tsx
│       │   └── r/[token]/
│       │       ├── page.tsx
│       │       └── gracias/page.tsx
│       ├── components/
│       ├── lib/
│       │   ├── api.ts               # cliente HTTP tipado
│       │   └── types.ts
│       └── hooks/
└── nginx/
    └── default.conf
```

---

## 12. Infraestructura

**`docker-compose.yml`** (producción) con servicios: `db`, `backend`, `frontend`, `nginx`.

Requisitos:
- `healthcheck` en `db` con `pg_isready`; `backend` con `depends_on: condition: service_healthy`.
- `restart: unless-stopped` en todos.
- El backend corre las migraciones de Alembic en el arranque (script `entrypoint.sh` que hace `alembic upgrade head` y luego lanza uvicorn).
- Uvicorn con `--workers 4`.
- Nginx enruta `/api/*` al backend y todo lo demás al frontend. Configura `client_max_body_size 10M` para las subidas de Excel y timeouts de 120s para las exportaciones.
- El puerto de Postgres **no** se expone al host en producción (solo en `docker-compose.dev.yml`).
- Volumen nombrado para Postgres.

**`.env.example`** con todas las variables documentadas con comentarios: puertos, credenciales de BD, `SECRET_KEY`, `NEXT_PUBLIC_BASE_URL`, `UMBRAL_APROBACION`, `COOKIE_SECURE`.

**`README.md`** con: requisitos previos, cómo clonar, cómo generar el `SECRET_KEY`, cómo levantar, cómo crear el usuario admin, cómo obtener la IP del servidor para `NEXT_PUBLIC_BASE_URL`, cómo hacer backup de la BD (`pg_dump`), y cómo actualizar desde git.

**`CLAUDE.md`** con las convenciones del proyecto: patrón de migraciones idempotentes, español para toda la UI y mensajes de error, nunca exponer `es_correcta` en endpoints públicos, agregaciones en SQL no en Python, y el mapa de puertos.

Incluye también un script `scripts/backup.sh` que haga `pg_dump` comprimido con fecha en el nombre, listo para cron.

---

## 13. Reglas de trabajo

- **Todo el texto visible al usuario en español**, incluidos mensajes de error de la API.
- **Comentarios y nombres de variables en español** cuando se refieran al dominio (`cuestionario`, `intento`, `puntaje`); en inglés lo genérico de infraestructura.
- Commits atómicos con mensajes descriptivos en español. Un commit por fase completada como mínimo.
- No dejes `console.log` ni `print` de depuración en el código final.
- Type hints completos en Python; sin `any` en TypeScript salvo justificación en comentario.
- Manejo de errores explícito: nada de `except: pass`.
- Si una decisión de diseño no está cubierta por esta especificación, **pregúntame antes de asumir**.

---

## 14. Plan de fases

Implementa en este orden. **Detente al terminar cada fase, resume lo hecho y espera mi confirmación.**

**Fase 1 — Andamiaje**
Estructura de carpetas, Docker Compose, Dockerfiles, `.env.example`, Nginx, backend FastAPI con `/api/health`, frontend Next.js con página placeholder, conexión async a Postgres verificada. Criterio: `docker compose up` levanta todo y `/api/health` responde.

**Fase 2 — Modelo de datos y auth**
Modelos SQLAlchemy, migración inicial de Alembic (idempotente), CLI `create-admin`, endpoints de auth con JWT en cookie, página de login, middleware de protección de rutas. Criterio: puedo crear el admin, iniciar sesión y ver una página protegida.

**Fase 3 — CRUD de cuestionarios**
Endpoints completos de cuestionarios/preguntas/opciones con validación de negocio, pestaña "Cuestionarios" con grid de tarjetas, modal de creación de dos pasos con constructor de preguntas y reordenamiento por arrastre, modo edición, duplicar y eliminar. Criterio: puedo crear un cuestionario con 5 preguntas y volver a abrirlo para editarlo.

**Fase 4 — Formulario público, QR y ligas**
Endpoints públicos con schemas que ocultan la respuesta correcta, rate limiting, página `/r/[token]` mobile-first con autoguardado y cola de reintentos, pantalla de gracias, modal de QR con descarga PNG, botón de copiar liga. Criterio: escaneo el QR desde un celular en la LAN, contesto el cuestionario, corto el WiFi a la mitad y las respuestas se recuperan al reconectar.

**Fase 5 — Importación de Excel**
Plantilla descargable, parser con reporte de errores por fila, integración en el modal de creación. Criterio: importo un Excel con 20 preguntas donde 2 filas están mal y veo el reporte correcto.

**Fase 6 — Dashboard de estadísticas**
Endpoints de agregación en SQL, tabla `metas_area` con su pantalla de captura, pestaña "Estadísticas" con KPIs, las 5 gráficas y la tabla paginada con filtros. Criterio: el dashboard refleja correctamente los datos de intentos reales.

**Fase 7 — Exportaciones**
Generación de Excel de 4 hojas y PowerPoint de 7 slides con gráficas nativas, botones de descarga. Criterio: ambos archivos abren sin advertencias de corrupción y contienen datos correctos.

**Fase 8 — Endurecimiento y documentación**
README completo, `CLAUDE.md`, script de backup, revisión de índices con `EXPLAIN ANALYZE` sobre las queries de estadísticas, prueba de carga básica de ~150 envíos concurrentes, revisión de que ningún endpoint público filtre respuestas correctas.

---

Empieza por la **Fase 1**. Antes de escribir código, dime qué puertos encontraste libres en el servidor y confirma que la estructura de carpetas propuesta te parece correcta.