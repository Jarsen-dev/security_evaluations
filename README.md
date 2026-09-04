# Sistema ESH

Sistema web interno del departamento de seguridad. Cubre tres cosas:

- **Evaluaciones de conocimientos.** El administrador arma los cuestionarios
  desde un panel; los operadores los contestan desde su celular escaneando un
  código QR, o desde una PC con la liga directa. **Quien responde no necesita
  cuenta.**
- **Controles ESH.** Los formatos de inspección que se llenaban en papel:
  presiones del Rayser, sustancias químicas peligrosas, almacén de residuos
  peligrosos, pláticas diarias de seguridad, recorridos perimetrales, revisión
  de muros, cuarto de silos EPS y tableros eléctricos —estos dos bilingües
  coreano/español—. Con semaforización automática, evidencia fotográfica y
  descarga en Excel con el mismo formato de la hoja original. Solo falta por
  habilitar el control de medicamento.
- **Estudios y capacitaciones.** El programa anual de estudios normativos:
  qué despacho los hace, con qué vigencia, en qué estatus van y cuándo
  vencen. Se descarga con el formato de la hoja DETALLE del archivo del
  departamento, y la campana del encabezado avisa un mes antes de cada
  vencimiento.

El panel se puede leer en **español, inglés y coreano**; se cambia con el
selector del encabezado. El formulario que contesta el personal de planta va
siempre en español.

- ~500 empleados, con picos de ~150 personas contestando en la misma hora.
- Corre en un servidor de planta y se publica en internet con un túnel de
  Cloudflare, para que se pueda contestar con datos móviles. La entrada por la
  IP de la LAN sigue existiendo como respaldo si el túnel se cae.
- Tolera cortes de WiFi: las respuestas se guardan solas al reconectar.

## Documentación

| Archivo | Para qué |
|---|---|
| `README.md` | Instalación y uso |
| `DESPLIEGUE.md` | Puesta en producción y operación del servidor |
| `SEGURIDAD.md` | Exposición pública, Cloudflare Access y revisión previa a repartir el QR |
| `CLAUDE.md` | Convenciones y trampas conocidas del código |
| `ESPECIFICACION.md` | Especificación original |

---

## Requisitos previos

| Requisito | Notas |
|---|---|
| Linux | Probado en Ubuntu 24.04 |
| Docker | 24 o superior |
| Docker Compose | v2.x. Si tienes el binario `docker-compose` (con guion) en vez del plugin `docker compose`, usa ese en todos los comandos de este README |
| Puertos libres | 8080 y 5150 en producción. En desarrollo también 3200, 8200 y 5442 |

Verifica qué puertos están ocupados antes de instalar:

```bash
ss -tulpn | grep -E ':(8080|5150|3200|8200|5442) '
```

Si alguno aparece, cámbialo en el `.env` (ver la sección de puertos).

---

## Instalación

### 1. Clonar

```bash
git clone <url-del-repositorio> evaluaciones
cd evaluaciones
```

### 2. Crear el archivo de configuración

```bash
cp .env.example .env
```

### 3. Generar la llave secreta

Los JWT de la sesión del administrador se firman con esta llave. **No dejes
la de ejemplo.**

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

Copia el resultado en la línea `SECRET_KEY=` del `.env`. Cambia también
`POSTGRES_PASSWORD` y actualiza la contraseña dentro de `DATABASE_URL`, que
debe coincidir.

### 4. Configurar la URL de las ligas

Este es el paso que más se equivoca. La variable `NEXT_PUBLIC_BASE_URL` es la
URL que se codifica en los códigos QR: **si queda en `localhost`, el QR apunta
al propio celular del operador y no abre nada.**

Obtén la IP del servidor en la LAN:

```bash
hostname -I | awk '{print $1}'
```

Y ponla en el `.env` junto con el puerto de Nginx:

```
NEXT_PUBLIC_BASE_URL=http://192.168.1.50:8080
```

> Next.js incrusta esta variable durante la compilación. **Si la cambias
> después, hay que reconstruir el frontend** (`docker compose up -d --build
> frontend`); reiniciar no basta.

### 5. Levantar el sistema

```bash
docker compose up -d --build
```

El backend aplica las migraciones de Alembic automáticamente al arrancar.

Verifica que todo esté arriba:

```bash
docker compose ps                          # los 4 servicios, db "healthy"
curl http://localhost:8080/api/health      # {"status":"ok","db":"ok",...}
```

### 6. Crear el superadministrador

No hay registro público: el primer usuario se crea por línea de comandos.

```bash
docker compose exec backend python -m app.cli create-admin --username admin
```

Pide la contraseña por teclado (mínimo 8 caracteres) y no la muestra al
escribir. **No se acepta como argumento a propósito**: quedaría registrada en
el historial del shell y en la lista de procesos.

Este usuario nace como **superadministrador**: es el único que ve la pestaña
de Administración y, desde ahí, da de alta al resto del personal sin volver a
tocar la terminal. La CLI queda como vía de rescate.

Ya puedes entrar en `http://<ip-del-servidor>:8080/login`.

---

## Uso diario

### Crear una evaluación

1. Entra al panel y pulsa **Nuevo cuestionario**.
2. **Paso 1:** nombre y descripción. Marca si permites varios intentos por
   empleado (por defecto, cada número de empleado responde una sola vez).
3. **Paso 2:** captura las preguntas, o impórtalas desde Excel. Cada pregunta
   necesita mínimo 2 opciones y exactamente una marcada como correcta.
   Reordénalas arrastrando el asa `⠿`.

Los tres campos de identidad (nombre, número de empleado y área) se piden
siempre y no se configuran: aparecen atenuados en el constructor como
recordatorio.

### Importar preguntas desde Excel

Descarga la plantilla desde el propio constructor. Reglas del formato:

- Una hoja llamada `Preguntas`, una pregunta por fila.
- `Opcion 1` y `Opcion 2` obligatorias; de la 3 a la 5, opcionales.
- En `Respuesta Correcta` va el **número** de la opción (1–5) o su **texto
  exacto**. No importan los espacios ni las mayúsculas.
- Las filas con la columna `Pregunta` vacía se saltan (sirven de separador).
- Máximo 200 preguntas por archivo.

Si una fila tiene errores, **el resto sí se importa** y el sistema muestra el
número de fila de cada problema para que corrijas tu Excel.

### Compartir la evaluación

Cada tarjeta tiene tres formas de repartirla:

- **QR** — código para escanear con el celular, con opción de descargar el PNG
  para imprimirlo y pegarlo en el área.
- **Liga escritorio** — copia la URL al portapapeles para PCs.
- **Imprimir** — descarga el cuestionario en PDF para contestarlo en papel,
  para quien no trae celular. Ábrelo y elige la impresora desde tu visor.
  La hoja sale en blanco: incluye los tres campos de identidad, las áreas
  como casillas y todas las preguntas con sus opciones, **sin marcar la
  respuesta correcta**.

Las dos primeras apuntan a `http://<servidor>:8080/r/<token>`.

> Las hojas contestadas en papel se califican a mano: el sistema no las lee.
> Si necesitas que cuenten en las estadísticas, alguien tiene que capturarlas
> desde la liga pública.

El token es aleatorio, no se deriva del identificador del cuestionario y no se
puede adivinar. Para dejar de recibir respuestas, usa **Desactivar** en el menú
de tres puntos.

### Revisar resultados

La pestaña **Estadísticas** muestra KPIs, cinco gráficas y la tabla de
intentos, todo filtrable por área y rango de fechas.

Para que el "nivel de participación" tenga sentido hay que capturar cuánta
gente hay en cada área: botón **Configurar metas por área**. Las áreas sin meta
muestran su conteo absoluto y ocultan el porcentaje.

Los botones **Descargar Excel** y **Descargar PowerPoint** exportan lo que
estés viendo, respetando los filtros activos.

---

## Mapa de puertos

| Servicio | Puerto interno | Puerto en el host | Expuesto en producción |
|---|---|---|---|
| Nginx | 80 | **8080** | **Sí — único punto de entrada** |
| Frontend (Next.js) | 3000 | 3200 | No |
| Backend (FastAPI) | 8000 | 8200 | No |
| PostgreSQL | 5432 | 5442 | No |
| pgAdmin | 80 | 5150 | Sí, solo en la LAN |

En producción se publican el 8080 y el 5150 (pgAdmin, alcanzable **solo desde
la LAN de la planta**: el túnel de Cloudflare no lo publica y ese puerto no
debe abrirse en el firewall hacia internet). Los demás solo se abren con el
compose de desarrollo, para depurar.

> **Entra siempre por el 8080.** Si abres el frontend directo en el 3200, las
> páginas cargan pero las llamadas a `/api/*` fallan: es Nginx quien separa el
> tráfico entre el backend y el frontend.

Todos los puertos se cambian desde el `.env`. El proyecto declara su propio
nombre de Compose (`evaluaciones`), su red (`evaluaciones_net`) y su volumen
(`evaluaciones_pgdata`) para no chocar con otros proyectos del servidor.

---

## Operación

### Comandos frecuentes

```bash
docker compose ps                      # estado de los servicios
docker compose logs -f backend         # seguir los logs del backend
docker compose restart backend         # reiniciar solo el backend
docker compose down                    # detener (los datos se conservan)
docker compose down -v                 # detener Y BORRAR LA BASE DE DATOS
```

### Usuarios del panel

Lo normal es hacerlo desde **Administración → Usuarios**: alta, edición de
permisos, desactivar y eliminar. Al crear a alguien se marca a qué pestañas
entra y si puede editar dentro de ellas (sin esa marca solo ve y crea).
Desactivar cierra sus sesiones abiertas al instante.

La CLI queda para lo que la interfaz no puede hacer a propósito: otorgar el rol
de superadministrador y recuperar el acceso si se pierde.

```bash
docker compose exec backend python -m app.cli listar-admins
docker compose exec backend python -m app.cli create-admin --username otro
# Contraseña olvidada:
docker compose exec backend python -m app.cli create-admin --username admin --reestablecer
```

### Catálogo de insumos

La pestaña **Catálogo** guarda los insumos de seguridad de la planta:
medicamento, EPP, señalización y extintores. De cada uno se registra su
proveedor, su ubicación, los topes de inventario y dos números que conviene no
confundir.

**El código puede repetirse.** Un mismo código de proveedor ampara varios
productos, y lo que los distingue es la **descripción**: por eso es obligatoria
y no puede haber dos insumos con el mismo código y la misma descripción. Al
recibir mercancía, el sistema ofrece las descripciones de ese código y propone
la que más se parece a lo que dice la remisión; si no está seguro, deja la
elección al operador y no permite guardar hasta que elija.

Los dos números:

- **Piezas por caja**: cuántas pastillas, tabletas o unidades trae cada caja o
  paquete. Es un dato del producto y solo cambia si el proveedor cambia la
  presentación.
- **Existencia**: el inventario real, en piezas sueltas. Lo suman las
  recepciones —las cajas capturadas por las piezas de cada una— y se corrige
  aquí a mano tras el conteo físico.

El color de la columna Estado sale del servidor, no del navegador, y se mide
contra el máximo:

| Color | Significa |
|---|---|
| Verde — Normal | Del 75 % del máximo hacia arriba |
| Amarillo — A la mitad | Entre el 35 % y el 75 % |
| Rojo — Bajo | Por debajo del 35 %, o por debajo del mínimo capturado |
| Naranja — Excedido | Hay más de lo que se planeó almacenar |
| Gris — Sin topes | El insumo no tiene máximo: no hay contra qué medirlo |

El filtro de estado sirve para armar la lista de compra de un vistazo.

Para cargar varios de golpe, **Descargar plantilla**, llenarla y **Importar
desde Excel**. Los insumos nuevos se dan de alta y los que ya existían se
corrigen con lo que el archivo traiga distinto —categoría, unidad de medida,
proveedor, ubicación, piezas por caja, mínimo y máximo—, así que el mismo Excel
sirve para corregir en bloque sin abrir los insumos uno por uno. Dos cosas no
se tocan: la **existencia**, que la mueven las recepciones y se corrige desde
el panel, y las **columnas que el archivo no traiga**, que se quedan como
están. Las filas con problemas se reportan con su número para corregirlas en el
origen.

Las entradas no se capturan aquí: se fotografían en **Inventario → Recepciones**
y la pestaña **Inventario → Stock** muestra el resultado, con los mismos
filtros y la fila teñida según el semáforo. Las salidas se registran en
**Controles → Control de Insumos**: se elige el insumo, a quién se le entrega,
el área y cuánto se usó, y el consumo baja del stock. Lo que se mide a granel
(GR, ML, MTS) pregunta antes si el envase se terminó: si no, el uso queda
registrado pero el inventario no baja, porque lo que cuenta son piezas.

### Extintores

**Controles → Extintores** lleva la ficha de cada extintor de la planta:
folio, modelo, capacidad, tipo (CO2 o P.Q.S.), ubicación y fecha de
vencimiento. La tabla se pagina de 50 en 50 y se filtra por texto, tipo, estado
del vencimiento y si ya se revisó hoy; arriba dice cuántos llevan revisión del
día sobre el total.

El **vencimiento se semaforiza solo**: amarillo a dos meses, rojo el último mes
y en cuanto pasa la fecha. Lo que entra en el último mes aparece además en la
campana del encabezado.

Cada extintor tiene su **etiqueta QR de 3 × 3 cm**. Desde el botón del código se
imprime una sola o se añade a una cola, para no gastar una hoja entera en una
etiqueta; el PDF sale con todas las de la cola en una rejilla, con el folio y la
ubicación debajo de cada código.

La **revisión diaria** son doce puntos —ubicación, manómetro, cilindro,
manguera, boquillas, palanca, manija, etiqueta, válvula, presión, seguro y
cincho, y base— que se marcan como conforme o inconforme. Cada inconformidad
exige observación y al menos una foto. Al terminarla el icono de la fila pasa a
una palomita verde, y si hubo hallazgos aparece el botón de **cierre**, el mismo
de los demás controles. La revisión del día se puede corregir con permiso de
edición; las de días anteriores quedan cerradas.

Desde el celular no hace falta buscar el extintor en la tabla: se escanea su QR
con la cámara del teléfono y se abre directamente su revisión. El botón de la
cámara en el panel explica cómo, y ofrece un código para abrir la pestaña en el
teléfono.

El botón de **Excel** descarga tres hojas: la ficha de todos los extintores, las
revisiones del mes elegido con los doce puntos como columnas, y las evidencias
fotográficas de ese mes.

Eliminar un extintor borra su ficha pero **conserva sus revisiones**: siguen
saliendo en el Excel de los meses en que se revisó.

### Rondines de seguridad

La captura **la hace una app de AppSheet**, que es la que usan los guardias y
la que tiene pegados en la planta los 44 códigos QR. Este sistema no captura:
consume esos datos y aporta lo que AppSheet no hace —el tablero de matriz, el
cumplimiento medido contra los rondines que ya transcurrieron, el Excel del
turno y el correo de cambio de turno—.

**Puesta en marcha.**

1. Acuñar el secreto del webhook y capturarlo en el `.env` del servidor:

   ```bash
   openssl rand -base64 32     # → RONDINES_WEBHOOK_SECRETO
   ```

2. En AppSheet, crear un Bot que al agregarse una fila a `Hoja 1` llame al
   webhook:

   | | |
   |---|---|
   | URL | `https://esh.chwon.it.com/api/publico/rondin/escaneos` |
   | Método | `POST` |
   | Cabecera | `X-Rondines-Secreto: <el mismo secreto>` |

   El cuerpo debe mandar `id` (el `ID_Registro`), `numero` (el `Punto_QR`) y
   `escaneado_at` (el `Fecha_Hora`); lo demás —GPS, comentario, correo— viaja
   si se incluye y se guarda, pero no es obligatorio.

3. Cargar el catálogo y, si se quiere, el histórico:

   ```bash
   docker compose exec backend python -m app.cli importar-puntos \
       --archivo /tmp/Puntos_Referencia.csv
   docker compose exec backend python -m app.cli importar-escaneos \
       --archivo /tmp/Hoja1.csv
   ```

   Los dos son **idempotentes**: correrlos dos veces no duplica nada. Por eso
   `importar-escaneos` sirve además para **rellenar huecos** si el túnel se cayó
   o AppSheet agotó los reintentos: se reexporta el rango y se vuelve a correr.

**El catálogo de puntos es de solo lectura.** Los puntos se administran en
AppSheet; la pestaña *Rondines → Puntos de control* solo los muestra. Para
retirar uno, se quita allá y se corre `importar-puntos --desactivar-ausentes`:
se marca inactivo, nunca se borra, para que los turnos ya cerrados sigan
contando igual.

**El tablero.** El día que se elige es el de **inicio** del turno, no el del
calendario:

| Turno | Horario |
|---|---|
| Día | 07:30 → 19:30 del mismo día |
| Noche | 19:30 → 07:30 del día siguiente |

Para ver la noche del 25 al 26, se elige el **25** con turno **Noche**.

Cada turno tiene seis rondines de dos horas. Un recorrido se corta cuando pasan
más de 30 minutos sin escanear, y se asigna completo al rondín donde cayó la
mayoría de sus puntos: así un recorrido que cruza las 09:30 no se parte en dos
columnas. El tablero se refresca solo cada minuto mientras se está mirando.

**Un escaneo puede tardar en aparecer.** AppSheet captura sin señal y sincroniza
después, así que una ronda recién caminada puede no verse todavía. No es un
fallo del tablero: la hora que vale es la del escaneo, no la de la llegada, y
el sistema guarda las dos (`escaneado_at` y `recibido_at`).

**Reportes.** Se descarga el Excel del turno, o se manda por correo. Si se
capturan las variables `SMTP_*` y `RONDINES_REPORTE_AUTOMATICO=true` en el
`.env`, el sistema envía el reporte solo al cambio de turno. **Hoy está
apagado**: AppSheet ya tiene su propio «Envío de Reporte Diario», y encender
los dos manda dos correos.

### Actividad del sistema

**Administración → Logs** lista todo lo que se crea, edita o elimina, más los
inicios de sesión y los intentos fallidos, con filtros por fecha, hora y
usuario. Las consultas de lectura no se registran, y el formulario público
tampoco: ese ya deja su rastro en los intentos.

### Base de datos

**Administración → Mantenimiento** abre pgAdmin y copia las credenciales al
portapapeles. pgAdmin no admite iniciar sesión desde una liga externa (su
formulario exige un token propio), así que solo hay que pegarlas. El servidor
de la base viene precargado.

### Respaldos

El script `scripts/backup.sh` genera un volcado comprimido con la fecha en el
nombre y borra los que pasan de 30 días.

```bash
./scripts/backup.sh
```

Para programarlo todos los días a las 2 de la mañana:

```bash
crontab -e
# Agregar:
0 2 * * * /ruta/completa/al/proyecto/scripts/backup.sh >> /var/log/evaluaciones_backup.log 2>&1
```

Variables opcionales: `DIRECTORIO_BACKUPS` y `DIAS_RETENCION`.

**Restaurar** un respaldo:

```bash
gunzip -c backups/evaluaciones_20260817_020000.sql.gz | \
  docker exec -i evaluaciones_db psql -U evaluaciones -d evaluaciones
```

Copia los respaldos fuera del servidor con regularidad: un disco dañado se
lleva la base y sus respaldos juntos.

### Actualizar desde git

```bash
cd /ruta/al/proyecto
./scripts/backup.sh                    # primero el respaldo
git pull
docker compose up -d --build           # las migraciones corren solas
docker compose logs backend | tail -20 # confirmar que arrancó
```

---

## Desarrollo

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

Diferencias con producción: recarga en caliente del backend y del frontend, el
código montado desde el host, y los puertos de db/backend/frontend publicados.

Documentación interactiva de la API: `http://localhost:8080/api/docs`

Conectarse a la base de datos en desarrollo:

```bash
psql -h localhost -p 5442 -U evaluaciones -d evaluaciones
```

---

## Solución de problemas

**El código QR no abre desde el celular.**
`NEXT_PUBLIC_BASE_URL` tiene `localhost` o la IP equivocada. Corrígela y
reconstruye el frontend: `docker compose up -d --build frontend`. Comprueba
también que el celular esté en la misma red y que el firewall permita el 8080.

**"Estás enviando demasiadas peticiones" durante una evaluación masiva.**
El límite es de 30 peticiones por minuto y por IP. Si la WiFi de planta hace
NAT, todos los celulares llegan con la misma IP y se bloquean entre sí. Sube
`RATE_LIMIT_PETICIONES` en el `.env` y reinicia el backend, o quita el NAT del
segmento de los operadores.

**El login no funciona.**
Confirma que estás en el puerto **8080** y no en el del frontend. Si la
contraseña se te olvidó, reestablécela con la CLI. Revisa que `COOKIE_SECURE`
esté en `false`: con `true` sobre HTTP el navegador descarta la cookie.

**El backend no arranca.**
`docker compose logs backend`. Lo más común es que `DATABASE_URL` no coincida
con `POSTGRES_PASSWORD`, o que falte el driver async en la URL
(`postgresql+asyncpg://`).

**Un empleado no puede volver a contestar.**
Es la regla de intento único. Si necesitas permitirlo, edita el cuestionario y
activa "Permitir varios intentos por empleado".
