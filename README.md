# Sistema ESH

Sistema web interno del departamento de seguridad. Cubre dos cosas:

- **Evaluaciones de conocimientos.** El administrador arma los cuestionarios
  desde un panel; los operadores los contestan desde su celular escaneando un
  código QR, o desde una PC con la liga directa. **Quien responde no necesita
  cuenta.**
- **Controles ESH.** Los formatos de inspección que se llenaban en papel:
  presiones del Rayser, inspección de sustancias químicas peligrosas, almacén
  de residuos peligrosos, pláticas diarias de seguridad, recorridos
  perimetrales y revisión de muros. Con semaforización automática, evidencia
  fotográfica y descarga en Excel con el mismo formato de la hoja original.
  Los tres controles que faltan del recorrido diario ya aparecen como pestañas
  y se irán habilitando.

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
