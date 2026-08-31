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

**En coreano, cada texto lleva el español debajo como subtítulo.** En planta
conviven las tres lenguas y quien lee hangul no siempre lee español, pero quien
está al lado sí: con el panel en 한국어, el resto del turno se quedaba sin poder
leer la pantalla.

El mecanismo son dos piezas, y la separación entre ellas no es negociable:

- `t()` **sigue devolviendo `string`**. En coreano devuelve el hangul y el
  español pegados con un salto de línea. Tiene que seguir siendo un string
  porque de sus ~876 llamadas, más de doscientas acaban en un `placeholder`, un
  `aria-label`, un `title`, un toast o un mensaje de zod, donde no cabe markup.
  Ahí el salto de línea es justo lo que se quiere: dos renglones.
- `bilingue()` (en `lib/i18n/bilingue.tsx`) parte ese string en dos `<span>` y
  pinta el español más chico. **Va donde el texto se pinta, no donde se
  traduce.** Deja pasar de largo lo que no sea un string con separador, así que
  es idempotente.

Al escribir un componente del panel:

- **Todo `t()` que caiga como hijo de JSX va envuelto: `{bilingue(t('x.y'))}`.**
  Sin el envoltorio el texto se ve igual de grande y en un solo renglón.
- Las props de las primitivas (`Input`, `Textarea`, `Modal`, `Pestanas`,
  `Toast`, `TarjetaKPI`) **no** se envuelven en el llamador: siguen tipadas
  `string` y el `bilingue()` va adentro. `etiqueta={t('x')}` se queda tal cual.
- Los atributos del DOM tampoco: `placeholder`, `title`, `alt` y `aria-label`
  reciben el string de dos renglones y así se quedan.
- `unaLinea()` es para lo que no admite ni siquiera el salto: las leyendas y los
  tooltips de recharts (son SVG y lo colapsan a un espacio), un `t()` incrustado
  a media plantilla (`` `${t('comun.fecha')}: ${fecha}` ``) y un `t()` que viaja
  como valor de interpolación **dentro de otro** `t()`.
- Si el coreano y el español coinciden —siglas, «OK», «QR», o una clave que
  todavía falta en `ko.ts`— no se duplica: `t()` lo detecta comparando.

El tamaño sale del token `subtitulo` de `tailwind.config.ts`, definido en `em`
para encogerse respecto al texto que acompaña. Y por eso mismo el `content` de
Tailwind incluye `./src/lib/**`: sin esa línea no ve las clases de
`bilingue.tsx`, no las genera y el subtítulo sale del mismo tamaño que el
hangul **sin que nada falle de forma visible**. Pasó.

### 7. El sistema está publicado en internet

Un túnel de Cloudflare sirve el sitio en `https://esh.chwon.it.com`.
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
  rutas `controles` e `inventario`. PCI MTTO cuelga de ese mismo prefijo, así
  que no estrena nada ni hace falta dar de alta una aplicación nueva. Después estrenaron prefijo propio
  Administración (`api/administracion` y la ruta `administracion`), Estudios
  (`api/estudios` y la ruta `estudios`), Catálogo (`api/catalogo` y la ruta
  `catalogo`), Rondines (`api/rondines` y la ruta `rondines`) e Inventario
  (`api/inventario`, sobre la ruta `inventario` que ya existía). **Sus
  aplicaciones de Access todavía están pendientes de crear**; queda anotado en
  `SEGURIDAD.md`.

El límite de tasa distingue dos cuotas (`core/ratelimit.py`): la amplia de
`/api/publico` y una estricta de 5 fallos por 5 minutos en `/api/auth/login`.
En el login **solo cuentan los 401**, para que un admin no se autobloquee.

`SEGURIDAD.md` tiene el detalle: configuración de Access, revisión previa a
repartir el QR, vigilancia y los riesgos que el diseño acepta.

### 8. Los permisos los aplica la API, no el panel

Tener sesión ya no da acceso total. Cada usuario lleva en `admin_users.permisos`
un JSON por módulo (`cuestionarios`, `controles`, `inventario`, `estudios`,
`catalogo`, `rondines`): **estar presente** es el acceso de ver y crear,
`editar` agrega modificar y eliminar. El superadministrador (`es_superadmin`)
puede todo y es el único que ve `/administracion`.

La decisión vive en **un solo lugar**, `AdminUser.puede()`. La capa HTTP la
traduce con la fábrica `requiere()` de `api/deps.py`:

```python
router = APIRouter(dependencies=[Depends(requiere("cuestionarios"))])

@router.delete(
    "/cuestionarios/{id}",
    dependencies=[Depends(requiere("cuestionarios", editar=True))],
)
```

Al agregar un endpoint que **modifica o elimina**, repite la dependencia con
`editar=True`. Los `POST` que solo crean se quedan con el acceso simple.

El panel esconde pestañas y botones (`useSesion().puede()` y `GuardiaModulo`),
pero eso es **cosmética**: sirve para no ofrecer acciones que devolverían 403,
no para autorizar. Nunca muevas una comprobación de la API al frontend.

Desactivar una cuenta corta el acceso de inmediato: `obtener_admin_actual`
revisa `activo` en cada petición, y el login también lo comprueba (después de
verificar la contraseña, para no delatar qué cuentas existen).

Dar de alta a alguien desde el panel **nunca** crea un superadministrador: ese
rol solo se otorga con `python -m app.cli create-admin`. A cambio, el servicio
impide eliminar o desactivar al último superadministrador activo, y que uno se
quite a sí mismo; sin esas guardas el sistema se queda sin quien lo administre
y solo se recupera por SSH.

### 9. La bitácora se llena sola, y deja fuera las lecturas

`core/bitacora.py` es un middleware: escribe un renglón por cada petición que
**cambia datos** (POST/PUT/PATCH/DELETE con respuesta 2xx), más los inicios de
sesión y los intentos fallidos. Se hace ahí, y no llamando a un servicio desde
cada ruta, para que ningún endpoint nuevo se quede sin registrar por olvido.

Qué queda fuera, a propósito:

- **Las lecturas.** Son la mayoría del tráfico y su ruido escondería justo lo
  que se quiere auditar.
- **`/api/publico` completo.** Lo contesta el personal de piso, son cientos de
  peticiones por hora y ya dejan rastro en `intentos` y `respuestas`.

Para que un renglón diga *qué* se tocó y no solo la acción, la ruta llama a
`anotar(request, detalle=...)`; el catálogo de `core/bitacora.py` pone el resto.
Si agregas un endpoint que modifica, súmalo al catálogo: sin entrada se
registra igual, pero con una descripción genérica.

`username` se guarda **desnormalizado** en cada renglón (misma razón que
`responsable` en los controles ESH): borrar un usuario pone el FK en NULL y el
histórico quedaría anónimo justo cuando más importa.

La escritura va envuelta en un `try/except` que traga la excepción y la manda a
los logs. Es la **única** excepción justificada a la regla de no tragarse
errores, y está comentada como tal: la operación del usuario ya se completó y
ya se le respondió, así que perder el renglón es malo, pero deshacer un
cuestionario recién guardado por un fallo al auditarlo lo es mucho más.

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
| `core/` | Configuración, constantes, catálogos de los controles y de los estudios, seguridad, límite de tasa, bitácora, errores |

Las exportaciones viven en `services/`: `excel_export.py` y `pptx_export.py`
(reportes de estadísticas), `pdf_export.py` (cuestionario imprimible),
`controles_excel.py` (formatos de los controles ESH), `estudios_excel.py` (la
hoja DETALLE del programa de estudios) y `exportacion_comun.py` con lo que
comparten: estilos de hoja, la paleta del semáforo, la cabecera de descarga y
los helpers de fecha. Todas generan en `BytesIO` y se devuelven con
`StreamingResponse`: nada toca el disco del servidor.

**El PDF imprimible nunca marca la respuesta correcta.** Se le entrega a quien
va a contestar. `pdf_export.py` no debe leer `es_correcta` bajo ninguna
circunstancia (misma lógica que la regla 1).

**Controles ESH** (`api/routes/controles.py`, `services/control_service.py`)

Los formatos de inspección que antes se llenaban en papel. Cuatro reglas
propias:

- Los puntos de cada control y el rango de los manómetros viven en
  `core/controles_catalogo.py` y se sirven por la API, igual que las áreas: el
  frontend nunca los tiene escritos a mano.
- La semaforización (verde 125–135 psi, rojo abajo, naranja arriba) **se
  calcula en el servidor**. El frontend repite la regla solo para pintar el
  formulario mientras se teclea; lo que se guarda y lo que sale en el Excel lo
  decide el backend.
- **Los controles de lista de verificación son el mismo código.** Cinco hojas
  comparten tabla (`registros_checklist`), servicio, rutas
  (`/api/controles/checklist/{control}`), formulario y generador de Excel; lo
  único que las distingue es su `DefinicionChecklist` en el catálogo. Un
  control nuevo con esta forma se agrega ahí, no copiando componentes.

  Hay dos variantes, y lo que decide cuál es si la definición trae
  `encabezado`:

  | | Rejilla mensual | Formato por inspección |
  |---|---|---|
  | Hojas | Almacén de RP's, recorridos, muro | Silos EPS, tableros eléctricos |
  | Excel | Uno por mes, una fila por día | Uno por inspección, con la maqueta de la hoja |
  | Por día | Una sola | Varias: una por turno, o por tablero y turno |
  | Extras | — | Encabezado, categorías, mediciones y bloques al pie |

- **`discriminador` es lo que permite varias inspecciones el mismo día.** Lo
  arma el servicio con los campos que el catálogo marca en `clave_unicidad`
  (el turno en silos; el tablero y el turno en tableros) y queda vacío en las
  rejillas, así que la restricción `UNIQUE (control, fecha, discriminador)`
  significa "una hoja por día" para ellas sin que la base tenga que conocer
  ninguna clave de control. El encabezado y los bloques del pie van en dos
  columnas `JSONB` que valida el catálogo, no la base.
- **Las fotos viven todas en `controles_fotos`**, con un `CHECK` que obliga a
  que solo una de sus tres llaves foráneas venga llena (punto, plática o
  Rayser, cierre y PCI MTTO). Hay un solo endpoint que las sirve,
  `/api/controles/fotos/{id}`, y los listados **nunca** traen la columna
  `imagen`: un mes de evidencias son decenas de megabytes. Un control nuevo que
  necesite evidencia **suma su llave y rehace el `CHECK`** en una migración, en
  lugar de estrenar tabla propia.

**PCI MTTO** (`api/routes/controles.py`, `services/pci_service.py`,
`services/pci_automatico.py`)

El mantenimiento mensual al sistema contra incendios. Es el único control que
**no se puede dejar sin contestar**, y de ahí salen sus reglas propias:

- **No comparte tabla con los de lista de verificación.** Aquellos son hojas
  diarias de N puntos que solo admiten fotos; este es mensual, tiene una sola
  pregunta y guarda además un **documento** —el reporte del proveedor—, que no
  existía en ningún otro sitio del sistema. Por eso lleva tabla, servicio y
  panel propios.
- **La llave natural es `(anio, mes)`, y ese `UNIQUE` es el candado** de la
  tarea periódica. A diferencia del reporte de rondines, aquí no hace falta
  tabla de candado aparte: el efecto secundario *es* el `INSERT`, así que el
  primer worker que lo consigue cierra el mes y los otros tres reciben
  `IntegrityError`, hacen `rollback` y **siguen con el mes siguiente** —abortar
  se llevaría por delante los meses que aún faltan.
- **`ck_pci_motivo_obligatorio` es el CHECK que sostiene la regla de negocio.**
  El ingenuo —«si NO, entonces motivo»— rompería la tarea, que crea la fila
  precisamente sin motivo. La versión que sí funciona es
  `realizado OR motivo IS NOT NULL OR automatico`: un registro **manual** sin
  motivo es imposible, y el único hueco lo abre el cierre automático, que es
  justo el que el panel reclama. Lo que la base **no** puede sostener es «si sí,
  al menos una foto»: las fotos viven en otra tabla y un `CHECK` no cruza
  tablas, así que esa regla vive solo en el servicio.
- **`PCI_PRIMER_MES` es histórico y no se toca.** Va como constante versionada
  y no como configuración: bajarlo inventaría meses incumplidos que nadie pudo
  contestar, y subirlo borraría faltas reales.
- **Los registros no se borran, se corrigen** (`PUT`, con `editar=True`).
  Borrar un cierre automático no serviría de nada: la vigilancia lo levantaría
  otra vez en menos de una hora con el motivo en blanco.
- **`meses_a_cerrar()` es puro y está probado** (`tests/test_pci.py`). Excluye
  siempre el mes en curso y deja una hora de gracia sobre el cambio de mes, o
  quien esté subiendo un reporte de 10 MB a las 23:59 pierde la subida.

Dos trampas nuevas que estrena este control:

- **El nombre del archivo subido acaba en una cabecera HTTP.** Lo pone quien lo
  sube, y sin sanearlo unas comillas o un salto de línea permiten inyectar
  cabeceras: `sanear_nombre()` se queda solo con el nombre base, sin rutas ni
  caracteres de control.
- **El reporte se sirve SIEMPRE como `attachment` y con `nosniff`.** Se acepta
  cualquier formato, y el archivo sale del mismo origen que el panel y con la
  cookie de sesión: servido *inline*, un `.svg` o un `.html` subido como
  «reporte» sería XSS almacenado con robo de sesión. El endpoint de fotos se
  salva de esto porque su lista blanca son JPG y PNG.

El presupuesto de subida es una **suma**: Nginx corta en `client_max_body_size
25M` y el POST manda el documento y las fotos en el mismo multipart. Con 4
fotos de 2 MB más 10 MB de reporte son 18 MB. Subir cualquiera de los dos topes
sin subir el de Nginx haría que el proxy respondiera 413 —HTML crudo— antes de
llegar al backend, y el operador vería un error opaco en vez del mensaje en
español.

**Estudios y capacitaciones** (`api/routes/estudios.py`,
`services/estudio_service.py`)

El programa anual de estudios normativos, que antes vivía en un Excel. No es un
control ESH y por eso no cuelga de ellos: aquellos son un histórico de
inspecciones que no se toca, y cada renglón de aquí es un documento vivo que
cambia de estatus varias veces al año y se edita en su lugar.

- Las opciones de cada campo (vigencia, prioridad, IN/EX, estatus, vencimiento,
  aprobado y pagado) viven en `core/estudios_catalogo.py` y se sirven por la
  API, igual que las áreas y los puntos de los controles. Ahí va también el
  color del semáforo de cada opción: el panel y el Excel lo pintan, no lo
  deciden.
- Dos `CHECK` sostienen desde la base lo que también valida el servicio: la
  fecha de vencimiento existe **exactamente** cuando el vencimiento está "en
  curso", y el link solo acompaña a un estudio con estatus OK. El servicio
  descarta el campo que no aplica en lugar de rechazar la petición, así que el
  `CHECK` es la red, no el camino normal.
- Un estudio "en curso" cuya fecha ya pasó **no se cambia solo** a vencido: el
  dato capturado se respeta y el estado se deduce de la fecha.
- La campana del encabezado consulta `GET /api/estudios/avisos`, que devuelve lo
  que vence dentro de un mes natural (`sumar_un_mes()`) y lo ya vencido. La
  ventana la decide el backend; el frontend solo la dibuja.
- **La campana ya no es solo de Estudios.** Junta esa fuente con los meses sin
  explicar de PCI MTTO (`GET /api/controles/pci-mtto/avisos`). Al sumar una
  fuente nueva: pedirla **solo** si el usuario tiene ese módulo (si no, son 403
  en cada carga del panel), unir las peticiones con `Promise.allSettled` para
  que el fallo de una no deje la campana en blanco, y mandar **datos y no
  texto** desde el backend —la frase la arma el panel con `t()` e `Intl`
  (regla 6)—. La campana solo desaparece si no hay ninguna fuente disponible.

**Recepciones por foto** (`api/routes/inventario.py`,
`services/ocr_recepciones.py`, `services/recepcion_service.py`,
`services/plantilla_service.py`)

La pestaña de Inventario recibe mercancía fotografiando la remisión del
proveedor. Tres pasos deterministas más un LLM **de texto**: Tesseract lee la
foto, un clasificador TF-IDF local reconoce el formato, y el modelo acomoda en
JSON el texto que Tesseract ya leyó. Cinco reglas propias:

- **El LLM nunca ve la imagen.** Un modelo de visión alucina caracteres e
  inventa números de parte y cantidades que no están en el papel. Aquí el peor
  caso es un campo en `null`, que el operador llena mirando la foto; no un dato
  falso que nadie detecta. Es la decisión que hace auditable el módulo.
- **`extraer()` nunca lanza.** Tesseract ausente, imagen corrupta, LLM caído,
  JSON inválido: todo sale como `ResultadoExtraccion(ocr_ok=False, error=...)`
  con un mensaje para el operador, y la ruta responde **200**. El formulario
  abre en captura manual con la foto ya guardada. Un código de error haría que
  el frontend tratara como fallo lo que en realidad es "hazlo a mano".
- **La foto se guarda ANTES de leerla.** Si la extracción falla, nadie tiene
  que volver al almacén por la hoja.
- **El presupuesto de tiempo (100 s) debe quedar por DEBAJO del
  `proxy_read_timeout` de Nginx (120 s).** Si el proxy corta primero, el
  navegador recibe un 500 opaco en vez del 200 con `ocr_ok:false` que habilita
  la captura manual.
- **Tres límites separados** en `ocr_recepciones.py`: `MAX_EJEMPLOS_CURADOS`
  (2), `MAX_EJEMPLOS_AUTO` (4) y `MAX_EJEMPLOS_PROMPT` (2, y **solo curados**).
  El corpus de clasificación quiere muchos ejemplos; el prompt quiere pocos.
  Sin esa separación, cada documento aprendido haría la extracción más lenta.
  El umbral del clasificador (0.20) y los n-gramas de **carácter** están
  calibrados con documentos reales: no se tocan a ojo.

Confirmar una recepción **suma la existencia** de cada insumo con un
`UPDATE ... cantidad + :n` en SQL, no leyendo y reescribiendo: con cuatro
workers dos recepciones simultáneas del mismo insumo se pisarían.

**Rondines de seguridad** (`api/routes/rondines.py`,
`services/rondin_service.py`)

El guardia escanea un QR pegado en cada punto y el tablero arma la matriz de
puntos × seis rondines de dos horas. Cuatro reglas propias:

- **Los recorridos se cortan por punto repetido, no por reloj.** `asignar_rondines()`
  agrupa los escaneos y corta cuando pasan más de 30 minutos de silencio **o**
  cuando reaparece un punto que el grupo ya visitó: eso es lo que distingue
  "otra vuelta" de "la misma vuelta, más tarde". No cortar por frontera de
  bloque es deliberado: partiría en dos toda ronda que cruce las 09:30, que es
  exactamente lo que el voto por mayoría existe para evitar. Sin el corte por
  punto repetido, dos vueltas seguidas a menos de 30 minutos se fundían en una
  y la segunda visita a cada punto se descartaba en silencio.
- **El cumplimiento se mide contra los rondines TRANSCURRIDOS**, no contra los
  seis. A las 09:00 los bloques 3 a 6 todavía no han pasado y contarlos como
  faltas dejaba el indicador clavado por debajo del 17 % aunque el guardia
  fuera perfecto. `_rondines_transcurridos()` lo decide en el servidor; el
  panel y el Excel pintan los bloques futuros en neutro, nunca en rojo.
- **La matriz se une por `punto_id`, nunca por `punto_numero`.** Los números se
  reasignan (editando un punto, o borrándolo y dando de alta otro que tome el
  número libre) y con el número como llave los escaneos históricos saltaban a
  la fila de otro punto. `punto_numero` queda solo como respaldo del histórico
  cuyo punto se borró y tiene el FK en NULL.
- **Un turno pasado incluye los puntos retirados que tengan escaneos en él.**
  Si la matriz fuera solo los puntos activos de hoy, desactivar uno reescribiría
  el cumplimiento de todos los turnos ya cerrados y el Excel reenviado dejaría
  de coincidir con el que se mandó por correo.

El reporte automático consulta `contar_escaneos()` **antes** de tomar el
candado del turno: un turno sin un solo escaneo no manda correo, y no gastar el
candado permite reintentarlo si más tarde sí aparecen escaneos.

**Frontend** (`frontend/src/`)

El grupo de rutas `(panel)` comparte el encabezado con las pestañas
(Cuestionarios, Controles, Inventario, Estudios, Catálogo, Rondines y, solo
para el superadministrador, Administración). El encabezado las filtra con
`useSesion().puede()`. A su derecha van la campana de vencimientos y el
selector de idioma.

Estadísticas ya no es una ruta: es una sub-pestaña dentro de `/cuestionarios`,
y la vista activa viaja en la query (`?vista=estadisticas`). Controles hace lo
mismo con `?control=rayser`, Administración con `?seccion=logs`, Rondines con
`?seccion=puntos` e Inventario con `?seccion=historial`. Estudios y Catálogo no
llevan nada en la query: cada una es una sola tabla con su formulario.

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

**Nada que dependa de la hora o del navegador se calcula en el primer
render.** El contenedor del frontend corre en **UTC** y la planta en UTC-6, así
que el HTML del servidor y el del navegador no coinciden y Next tira
*"Text content does not match server-rendered HTML"*. Pasó con
`IndicadorTurno`: a las 15:00 el servidor pintaba 🌙 y el navegador ☀️. No se
arregla poniéndole `TZ` al contenedor —el servidor nunca puede saber la zona
horaria de quien mira—: se arranca en un valor neutro y se resuelve en un
`useEffect`, como ya hace `ProveedorIdioma` con el idioma de `localStorage`.

**La `t` del diccionario NO debe cambiar de identidad.** `ProveedorIdioma` la
expone como un `useCallback` estable que lee el idioma de un ref, y no como
parte del `useMemo` del contexto. Media docena de paneles traen `t` en el array
de dependencias de un `useEffect`; si cambiara al cambiar de idioma, esos
efectos volverían a correr. Pasó: `PanelChecklist` hace `setCatalogo(null)` ahí
dentro, y cambiar de idioma a media inspección desmontaba el formulario y
borraba los puntos marcados, las observaciones y las fotos todavía sin subir.
La pantalla se traduce igual porque el *valor* del contexto sí cambia y eso
basta para re-renderizar a los consumidores.

**`sin_zona()` convierte a UTC, no a la hora local.** Sirve para sellos de
tiempo, pero si lo que el reporte muestra ES la hora (como el tablero de
rondines, donde cada celda dice a qué hora pasó el guardia), sale corrido seis
horas. Ver el helper `_local()` de `services/rondines_excel.py`.

**El escaneo de un rondín no pasa por la bitácora.** Cae bajo `/api/publico`,
que está excluido a propósito, y ya deja su rastro en `escaneos_rondin`. La
página que lo recibe (`/p/[token]`) también debe estar excluida del matcher de
`middleware.ts`: sin eso rebota al login y ningún QR funciona.

**Una tarea del `lifespan` corre en CADA worker de uvicorn.** Con
`UVICORN_WORKERS: "4"`, un envío programado sale cuatro veces. El reporte
automático de rondines lo resuelve con un candado en la base
(`envios_reporte_rondin`): el primero que gana el INSERT envía y los demás
chocan. Cualquier tarea periódica nueva necesita el mismo cuidado —aunque no
siempre hace falta tabla aparte: en PCI MTTO el candado es el propio
`UNIQUE (anio, mes)` del registro, porque ahí el efecto secundario *es* el
INSERT y no un correo.

Y una variable de configuración nueva **no basta con declararla en
`config.py`**: hay que pasarla también en el bloque `environment:` de
`docker-compose.yml`, o el `.env` no llega al contenedor y la tarea corre con
el valor por omisión sin que nada lo diga. Ya pasó con las `SMTP_*`.

**openpyxl no acepta datetimes con zona horaria.** Las columnas son
`TIMESTAMPTZ`; usa `sin_zona()` de `services/exportacion_comun.py`.

**PostgreSQL no indexa las llaves foráneas solo.** Sin
`ix_respuestas_opcion_id`, borrar una opción recorría las 188 mil respuestas
(56 ms por opción, y una edición borra decenas).

**Las imágenes van a la base, no al disco.** El backend **no tiene ningún
volumen escribible**: `docker-compose.yml` no le monta ninguno y `static/` solo
trae el logo, así que cualquier archivo escrito muere con el contenedor. Las
evidencias de los controles (`controles_fotos`), las fotos de recepción
(`recepciones_fotos`) y los ejemplos del clasificador
(`recepciones_plantilla_ejemplos`) son todos columnas `BYTEA`, servidas por un
endpoint autenticado. Los listados **nunca** seleccionan la columna de la
imagen: `plantilla_service.corpus()` selecciona columnas sueltas justo por eso,
y además porque navegar una relación perezosa desde una sesión asíncrona
revienta con `MissingGreenlet`.

**Los borradores de Controles van a IndexedDB, no a `localStorage`.** Los
cuatro formularios de Controles autoguardan lo capturado (`lib/borradores.ts` y
`hooks/useBorrador.ts`) para que cambiar de pestaña, salir del panel o recargar
no borre media inspección. Tiene que ser IndexedDB porque el borrador incluye
las **fotos**, que son `File`: `localStorage` solo admite texto, obligaría a
pasarlas a base64 —un tercio más— y su cuota son ~5 MB, mientras que una hoja
de silos son 30 puntos × hasta `MAX_FOTOS` fotos de hasta 2 MB. IndexedDB las
guarda directo por clonado estructurado y **sí funciona fuera de contexto
seguro**, a diferencia de `crypto.randomUUID` (regla 5); aun así se prueba por
la IP de LAN, no por localhost. Ninguna función de `borradores.ts` lanza: sin
almacenamiento el formulario funciona igual, solo que sin red.

Dos cuidados al tocarlo: el borrador **no se escribe hasta haber intentado
leerlo** (si no, el formulario vacío del primer render pisa lo guardado), y la
clave lleva el `username` porque la laptop de planta es compartida y la
inspección a medias de alguien no debe reaparecer —ni archivarse— bajo otro
nombre.

**`getUserMedia` no sirve para tomar la foto de evidencia.** Es la misma
trampa de la regla 5 y una más encima: la API no existe por HTTP en la IP de
LAN, y aunque se entre por el dominio, Nginx manda
`Permissions-Policy: camera=()` y el navegador la bloquea. La captura se hace
con `<input type="file" accept="image/*" capture="environment">`, que abre la
cámara del celular sin necesitar contexto seguro, y el reescalado con
`<canvas>`, que tampoco lo necesita. Ver
`components/controles/rayser/CampoFoto.tsx`.

**asyncpg no acepta dos sentencias en un mismo `op.execute`.** Las prepara, y
PostgreSQL responde *"cannot insert multiple commands into a prepared
statement"*. En las migraciones va una sentencia por llamada; lo único que
puede llevar varias es un bloque `DO $$ ... $$`, que cuenta como una sola.

**El parser de formularios de Starlette crea SUS `UploadFile`.** No la subclase
de FastAPI. Al leer campos de archivos a mano con `await request.form()` hay
que comprobar contra `starlette.datastructures.UploadFile`: con la clase de
FastAPI, el `isinstance` descarta todas las fotos en silencio y el registro se
guarda sin evidencia.

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
| pgAdmin | 80 | 5150 | Sí, **solo en la LAN** (el túnel no lo publica) |

Evitar (ocupados por otros proyectos del servidor): 3000, 3001, 8000, 8001,
5432, 5433, 5050, 80, 11434. pgAdmin usa el 5150 y no el 5050, que es su
puerto habitual, justamente por eso.

---

## Antes de dar por terminado un cambio

```bash
docker compose up -d --build
curl http://localhost:8080/api/health
docker compose logs backend | tail -20      # sin trazas de error
```

Si tocaste endpoints públicos, repite la auditoría de la regla 1.
Si agregaste un endpoint, revisa que lleve su `requiere(...)` y que aparezca en
el catálogo de `core/bitacora.py` si modifica datos (reglas 8 y 9).
Si tocaste el panel, agrega primero la clave en `es.ts`: `npm run typecheck`
falla hasta traducirla también en `en.ts` y `ko.ts`.
Si tocaste el modelo de datos, prueba la idempotencia de la migración.
Si tocaste el frontend, **ábrelo por la IP de LAN**, no por localhost: es la
única forma de detectar los fallos de contexto no seguro (regla 5).
