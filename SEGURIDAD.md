# Seguridad y exposición pública

El sistema dejó de ser una aplicación de LAN: un túnel de Cloudflare lo publica
en `https://esh.chwon.it.com` para que los ~500 empleados contesten con
datos móviles. Este documento cubre lo que cambió con eso, cómo se cierra el
panel de administración y qué revisar antes de repartir el QR.

Para el despliegue y la operación normal, ver `DESPLIEGUE.md`.

---

## Qué está publicado y qué no

```
Internet → Cloudflare (HTTPS) → cloudflared → nginx:80 → API / frontend
```

El túnel publica **todo** el sitio, no solo el formulario. Esa es la razón de
las medidas de abajo: sin ellas, la pantalla de acceso al panel queda expuesta
a internet igual que el formulario.

| Ruta | Quién debe entrar |
|---|---|
| `/r/<token>` | Cualquiera con la liga. El token **es** la credencial |
| `/api/publico/*` | Igual que la anterior: lo consume el formulario |
| `/api/health`, `/api/areas`, `/api/static/*` | Público (sin datos sensibles) |
| `/login`, `/cuestionarios`, `/controles`, `/inventario` | Solo usuarios del panel |
| `/catalogo`, `/rondines` | Solo usuarios del panel, según sus permisos |
| `/api/publico/rondin/escaneos` | Solo el Bot de AppSheet. El **secreto de la cabecera** es la credencial |
| `/re/<sesion>`, `/api/publico/recepcion/*` | Cualquiera con el QR, **durante 10 minutos y una sola vez** |
| `/administracion` | Solo el superadministrador |
| `/api/auth/*`, `/api/cuestionarios/*`, `/api/preguntas/*`, `/api/estadisticas/*`, `/api/metas-area`, `/api/wifi`, `/api/controles/*` | Solo usuarios del panel, según sus permisos |
| `/api/catalogo/*`, `/api/rondines/*` | Solo usuarios del panel, según sus permisos |
| `/api/inventario/*` | Solo usuarios del panel, según sus permisos |
| `/api/administracion/*` | Solo el superadministrador |

`/api/wifi` devuelve la contraseña de la red en claro; exige sesión por eso.

`/api/controles/*` sirve los registros de los controles ESH, incluidas las
**fotos de evidencia** de todos ellos (`/api/controles/fotos/{id}`). Son
imágenes tomadas dentro de la planta: viven en la base de datos, entran en el
respaldo de `evaluaciones_pgdata` y solo se entregan con sesión abierta.

Ese respaldo crece con ellas: cada punto en NO OK admite hasta cuatro fotos de
2 MB, así que un mes de recorridos puede sumar cientos de megabytes. Conviene
vigilar el tamaño del volumen, no solo el de la base.

### Permisos: quién puede qué

Tener sesión ya no da acceso total. Cada usuario lleva en `admin_users.permisos`
un JSON por módulo (`cuestionarios`, `controles`, `inventario`, `catalogo`,
`rondines`):
**estar
presente** es el acceso de ver y crear, y `editar` agrega modificar y eliminar.
El superadministrador (`es_superadmin`) puede todo y es el único que ve
`/administracion`.

Quien decide es la API: cada router lleva `Depends(requiere(...))` y los
endpoints que modifican repiten la dependencia con `editar=True` (ver
`backend/app/api/deps.py`). El panel esconde pestañas y botones, pero eso es
cosmética — si alguien llama la API a mano recibe 403.

Desactivar una cuenta (`activo = false`) corta el acceso **de inmediato**:
`obtener_admin_actual` revisa el estado en cada petición, así que las sesiones
ya abiertas dejan de servir sin esperar a que venza el token, y el login
tampoco la deja entrar.

#### Extintores: una etiqueta impresa que apunta al panel

El QR pegado a cada extintor lleva
`https://esh.chwon.it.com/controles?control=extintores&extintor=<id>`. **No abre
ninguna ruta pública**: cae en el panel, así que el celular pasa por Cloudflare
Access y por el login la primera vez del día. Es deliberado — una revisión lleva
responsable y es dato del panel, no del formulario de piso — y significa que un
QR fotografiado por alguien de fuera no le sirve de nada.

El identificador que viaja en la etiqueta es la llave primaria del extintor, y
no un token: no da acceso a nada por sí solo, y lo único que se puede deducir de
él es que ese extintor existe.

`POST /api/controles/extintores/etiquetas` genera el PDF. Es un POST pese a no
cambiar nada, para que la cola de impresión quepa en el cuerpo; queda registrado
en la bitácora con su propia descripción.

**No se tocó `Permissions-Policy`.** La revisión desde el celular usa la cámara
nativa del teléfono, así que `camera=()` sigue cerrado en `nginx/default.conf`.
Si alguna vez se abre a `camera=(self)`, hay que anotarlo aquí y en CLAUDE.md.

#### Una excepción escrita: el Control de Insumos cruza de módulo

`POST /api/controles/insumos` registra una salida de almacén y **baja
`insumos.existencia`**, que es dato del catálogo. Quien lo hace necesita el
módulo `controles` y **no** necesita `catalogo` ni `inventario`. Es
deliberado —es la razón de ser de la pestaña: el almacenista entrega y el stock
baja— pero es la única puerta por la que se toca el catálogo desde fuera de él,
así que conviene tenerla escrita.

Lo que acota el riesgo:

- **Solo resta, nunca suma.** No hay forma de inflar una existencia desde aquí.
- **No puede dejar negativo.** La resta lleva su guarda en el mismo `UPDATE`;
  si no alcanza, se rechaza y la fila queda intacta.
- **Deja rastro doble e inmutable**: la fila de `registros_control_insumos` con
  su `responsable` y su `admin_id`, y un renglón de bitácora con el insumo, la
  persona, el área y cuánto se descontó. Los registros no se editan ni se
  borran desde el panel.
- **No da acceso de edición al resto del módulo**: el endpoint se queda con el
  permiso simple, sin `editar=True`.

`GET /api/controles/insumos/buscar` es el otro lado de la misma decisión: le
sirve datos del catálogo a un usuario que no tiene ese módulo. Por eso devuelve
un schema recortado —id, código, descripción, unidad y existencia— y **omite a
propósito** proveedor, ubicación, mínimo, máximo y el semáforo, que son
información comercial y de inventario que ese usuario no ve por su vía normal.
Exige al menos dos caracteres y devuelve como mucho veinte filas, para que no
sirva de volcado del catálogo.

Todo cuelga de `/api/controles`, que ya tiene su aplicación de Cloudflare
Access: **no se estrena prefijo y no hace falta dar de alta nada nuevo.**

### Bitácora

`/api/administracion/bitacora` expone quién creó, editó o eliminó qué, y los
inicios de sesión (incluidos los fallidos). La escribe un middleware
(`backend/app/core/bitacora.py`) y guarda IP y ruta de cada acción. **No**
registra lecturas ni nada de `/api/publico`: son la mayoría del tráfico y su
ruido escondería justo lo que se quiere auditar.

El nombre de usuario se guarda desnormalizado en cada renglón, así que el
histórico sigue diciendo quién fue aunque después se elimine la cuenta.

---

## 1. Cerrar el panel con Cloudflare Access

La sesión de la aplicación (JWT en cookie) sigue siendo la autorización real:
Access se pone **delante** para que la pantalla de login ni siquiera sea
alcanzable desde internet. Son dos capas independientes, a propósito.

En el dashboard de Cloudflare → **Zero Trust → Access → Applications**, crear
una aplicación **Self-hosted** por cada ruta del panel:

| Aplicación | Dominio | Ruta |
|---|---|---|
| Panel — login | `esh.chwon.it.com` | `login` |
| Panel — cuestionarios | `esh.chwon.it.com` | `cuestionarios` |
| Panel — controles | `esh.chwon.it.com` | `controles` |
| Panel — inventario | `esh.chwon.it.com` | `inventario` |
| API — auth | `esh.chwon.it.com` | `api/auth` |
| API — cuestionarios | `esh.chwon.it.com` | `api/cuestionarios` |
| API — preguntas | `esh.chwon.it.com` | `api/preguntas` |
| API — estadísticas | `esh.chwon.it.com` | `api/estadisticas` |
| API — metas | `esh.chwon.it.com` | `api/metas-area` |
| API — wifi | `esh.chwon.it.com` | `api/wifi` |
| API — controles | `esh.chwon.it.com` | `api/controles` |
| Panel — estudios | `esh.chwon.it.com` | `estudios` |
| API — estudios | `esh.chwon.it.com` | `api/estudios` |
| Panel — catálogo | `esh.chwon.it.com` | `catalogo` |
| Panel — rondines | `esh.chwon.it.com` | `rondines` |
| Panel — administración | `esh.chwon.it.com` | `administracion` |
| API — catálogo | `esh.chwon.it.com` | `api/catalogo` |
| API — rondines | `esh.chwon.it.com` | `api/rondines` |
| API — inventario | `esh.chwon.it.com` | `api/inventario` |
| API — administración | `esh.chwon.it.com` | `api/administracion` |

> **Pendiente.** Doce aplicaciones son nuevas y **todavía no están dadas de
> alta**: `controles`, `inventario`, `api/controles`, `api/inventario`,
> `estudios`, `api/estudios`, `catalogo`, `api/catalogo`, `rondines`,
> `api/rondines`, `administracion` y `api/administracion`. Mientras no se creen, esas rutas
> quedan fuera de Access y lo único que las defiende es la cookie de sesión más
> la comprobación de permisos: la pantalla de login del panel no aparece, pero
> la ruta sí es alcanzable desde internet. Las dos de administración son las
> más sensibles de la lista, porque desde ahí se dan de alta usuarios.
>
> `estadisticas` ya no necesita su propia aplicación porque ahora es una
> pestaña dentro de `/cuestionarios`; se puede borrar o dejar, no estorba.

Access cubre la ruta indicada y todo lo que cuelga de ella, así que
`api/cuestionarios` también protege `/api/cuestionarios/{id}/imprimir`.

En cada una, una sola política: **Allow**, con el criterio `Emails` y la lista
de correos de quienes administran (o `Emails ending in` con el dominio de la
empresa). Método de autenticación: **One-time PIN** si no hay Google Workspace
o Entra ID conectado; el correo recibe un código de 6 dígitos.

### Qué NO proteger

No crear aplicaciones de Access sobre estas rutas, o los empleados no podrán
contestar:

```
/r/            → el formulario
/re/           → la página que abre el QR para fotografiar una remisión
/api/publico/  → lo que el formulario, la captura por foto y el webhook de
                 rondines de AppSheet consumen. En particular
                 /api/publico/rondin/escaneos: AppSheet llama desde la nube de
                 Google y no puede resolver el SSO de Access, así que
                 protegerlo corta la ingesta de rondines en seco
/api/health    → lo usa el healthcheck del contenedor
/api/areas     → lo pide el formulario para el selector de área
/api/static/   → el logo
/_next/        → el JavaScript y CSS del formulario
```

La forma segura de lograrlo es la de la tabla de arriba: proteger rutas
concretas del panel en vez de proteger `/` completo y luego abrir huecos. Un
hueco olvidado en `/_next/` deja el formulario en blanco y nadie puede
contestar.

### Verificar que quedó bien

Desde una red cualquiera, sin haber pasado por Access:

```bash
# Debe redirigir a la pantalla de Cloudflare Access (302), no mostrar el login
curl -sI https://esh.chwon.it.com/login | head -1
curl -sI https://esh.chwon.it.com/api/estadisticas/resumen | head -1

# Debe seguir funcionando sin pedir nada
curl -s  https://esh.chwon.it.com/api/health
curl -sI https://esh.chwon.it.com/r/<token-de-un-cuestionario> | head -1
```

El panel sigue funcionando igual en el navegador: tras autenticarse en Access,
la cookie `CF_Authorization` viaja en cada petición del mismo dominio, así que
las llamadas del panel a `/api/...` pasan solas.

---

## 2. Cambiar la contraseña del administrador

**Esto es lo más urgente.** El usuario quedó con `admin` / `admin123` desde el
desarrollo, y ese login es alcanzable desde internet.

```bash
docker compose exec backend python -m app.cli create-admin --username admin --reestablecer
```

Pide la contraseña por stdin: no se pasa como argumento porque quedaría en el
historial de bash. Usa una larga y única; no hay recuperación por correo.

---

## 3. Lo que ya quedó configurado en el repo

| Medida | Dónde | Qué resuelve |
|---|---|---|
| Límite de tasa en el login: 5 fallos por IP cada 5 min | `backend/app/core/ratelimit.py` | Antes se podían probar ~250 contraseñas por minuto: el limitador solo cubría `/api/publico` |
| `/api/docs` y `/api/openapi.json` apagados en producción | `backend/app/main.py` | Ya no se publica el mapa completo de endpoints del panel |
| `COOKIE_SECURE=true` | `.env` | La cookie de sesión no viaja jamás en claro |
| HSTS y `Permissions-Policy` | `nginx/default.conf` | El navegador se niega a hablar HTTP con el dominio |
| IP real del cliente vía `CF-Connecting-IP` | `nginx/default.conf` | Sin esto el túnel hacía que todos los celulares compartieran una IP y se bloquearan entre ellos |
| Rotación de logs (10 MB × 5 por servicio) | `docker-compose.yml` | El driver json-file crecía sin tope |

Los intentos fallidos de login cuentan cuota; los exitosos no, así que un
administrador no se autobloquea. El límite es por worker de uvicorn (son 4),
de modo que el tope real por IP ronda 20 fallos cada 5 minutos.

---

## 4. Publicar los cambios y revisar

El túnel corre en el servidor Ubuntu de producción, no en la máquina de
desarrollo: mientras no se despliegue ahí, nada de lo anterior está activo.
`.env` no viaja por git, así que las variables nuevas (`ENVIRONMENT`,
`RATE_LIMIT_LOGIN_*`) y las que cambiaron (`COOKIE_SECURE`,
`NEXT_PUBLIC_BASE_URL`) hay que capturarlas a mano en el `.env` del servidor,
tomándolas de `.env.example`.

```bash
cd /opt/evaluaciones
./scripts/backup.sh
git pull
# editar .env con las variables nuevas antes de reconstruir
docker compose up -d --build
```

El `--build` es obligatorio, no solo un reinicio: Next.js incrusta
`NEXT_PUBLIC_BASE_URL` en el bundle durante la compilación. Sin reconstruir,
los códigos QR seguirían apuntando a la IP de la LAN.

Ya en el servidor:

```bash
docker compose up -d --build
curl -s  https://esh.chwon.it.com/api/health          # {"status":"ok","db":"ok"}
curl -sI https://esh.chwon.it.com/api/docs | head -1  # 404
curl -sI https://esh.chwon.it.com/ | grep -i strict-transport-security
docker compose logs backend | tail -20                          # sin trazas de error
```

Y a mano, desde un celular con datos móviles (no con la WiFi de planta):
escanear el QR, contestar el cuestionario completo y confirmar que el resultado
aparece en el panel. Es la única prueba que cubre la cadena entera.

Lista corta:

- [ ] Cambios desplegados en el servidor (`git pull` + `--build`) y `.env`
      del servidor actualizado con las variables nuevas.
- [ ] Contraseña de `admin` cambiada.
- [ ] Aplicaciones de Access creadas y verificadas con los `curl` de arriba,
      **incluidas las doce nuevas** de `controles`, `inventario`,
      `api/controles`, `estudios`, `api/estudios`, `catalogo`, `api/catalogo`,
      `rondines`, `api/rondines`, `api/inventario`, `administracion` y
      `api/administracion`.
- [ ] `/r/<token>` abre sin pedir nada desde una red externa.
- [ ] `NEXT_PUBLIC_BASE_URL` es el dominio y el frontend se reconstruyó después
      de cambiarlo (Next incrusta esa variable en el build, no la lee en
      runtime).
- [ ] Un cuestionario contestado de punta a punta desde datos móviles.
- [ ] `RONDINES_WEBHOOK_SECRETO` capturado en el `.env` del servidor y el mismo
      valor en la cabecera del Bot de AppSheet.
- [ ] Prueba de humo del webhook: secreto equivocado ⇒ **401**, secreto correcto
      ⇒ **202**, secreto vacío en el servidor ⇒ **503**.

  ```bash
  curl -s -o /dev/null -w '%{http_code}\n' -X POST \
    https://esh.chwon.it.com/api/publico/rondin/escaneos \
    -H 'Content-Type: application/json' \
    -H 'X-Rondines-Secreto: incorrecto' -d '{}'
  ```
- [ ] Un escaneo real hecho en la app de AppSheet aparece en el tablero.

---

## 5. Vigilancia durante la campaña

La bitácora del panel (**Administración → Logs**) es ahora la primera parada:
filtra por fecha, hora y usuario sin entrar al servidor. Lo de abajo sigue
sirviendo para lo que la bitácora no cubre.

```bash
# Intentos de acceso fallidos (también salen en la bitácora, como sesion.fallida)
docker compose logs backend | grep -E "Contraseña incorrecta|usuario inexistente|cuenta desactivada"

# Puntos de rondín escaneados en el turno en curso
docker compose exec db psql -U evaluaciones -d evaluaciones -c \
  "SELECT punto_numero, escaneado_at AT TIME ZONE 'America/Monterrey' AS hora
     FROM escaneos_rondin ORDER BY escaneado_at DESC LIMIT 30;"

# Latencia de la ingesta de AppSheet: unos minutos es normal (sincroniza sin
# señal); varias horas de forma sistemática es que el Bot dejó de disparar.
# Una latencia NEGATIVA o de días sobre un escaneo suelto merece una mirada:
# es lo que se vería si alguien con el secreto fabricara una visita pasada.
docker compose exec db psql -U evaluaciones -d evaluaciones -c \
  "SELECT origen_id, punto_numero,
          escaneado_at AT TIME ZONE 'America/Monterrey' AS capturado,
          recibido_at - escaneado_at AS latencia
     FROM escaneos_rondin
    WHERE recibido_at - escaneado_at > interval '6 hours'
    ORDER BY recibido_at DESC LIMIT 30;"

# Intentos de ingesta con el secreto equivocado
docker compose logs backend | grep "Ingesta de rondines: secreto inválido"

# Renglones que AppSheet mandó y se descartaron (punto desconocido, fecha
# ilegible): si aparecen puntos nuevos, el catálogo quedó viejo y toca correr
# `importar-puntos`.
docker compose logs backend | grep "Ingesta de rondines:"

# Quién cambió qué, sin abrir el panel
docker compose exec db psql -U evaluaciones -d evaluaciones -c \
  "SELECT creado_at, username, accion, descripcion, ip
     FROM bitacora ORDER BY creado_at DESC LIMIT 50;"

# IPs frenadas por el límite de tasa
docker compose logs nginx | grep " 429 "

# Envíos por IP: una IP con decenas de intentos finalizados no es una persona
docker compose exec db psql -U evaluaciones -d evaluaciones -c \
  "SELECT ip_origen, COUNT(*) FROM intentos GROUP BY ip_origen ORDER BY 2 DESC LIMIT 20;"
```

En el dashboard de Cloudflare, **Analytics → Traffic** muestra el volumen y los
países de origen. Tráfico desde fuera de México sobre `/r/` merece una mirada:
el QR se reparte dentro de la planta.

---

## 6. Riesgos que este diseño acepta

No son defectos por corregir, son decisiones tomadas a conciencia. Quedan
escritas para que la siguiente persona no las descubra a media campaña.

**La contraseña de pgAdmin viaja al navegador.**
`GET /api/administracion/mantenimiento` devuelve el usuario y la contraseña de
pgAdmin en claro. Es lo que hace útil al botón de "copiar credenciales":
pgAdmin no admite iniciar sesión desde una liga externa porque su formulario
exige un token CSRF propio. Solo la recibe una sesión de superadministrador y
la ruta va detrás de Access, pero es una credencial de base de datos saliendo
de la API. Si alguna vez estorba, la alternativa es quitar la contraseña de la
respuesta y que se teclee a mano.

**pgAdmin escucha en la LAN de la planta.** Es el único puerto del stack, junto
al de Nginx, que se publica al host (`5150`). El túnel **no** lo publica —
`cloudflared` apunta solo a `nginx:80` — y **no debe abrirse en `ufw`** hacia
internet. Dentro de la planta, cualquiera que llegue a `http://<ip>:5150` ve la
pantalla de login de pgAdmin; por eso el contenedor se deja en `SERVER_MODE`
(el valor por omisión) y no en modo escritorio, que entraría sin pedir nada.

**Crear usuarios no puede crear superadministradores.** El alta desde el panel
siempre nace con `es_superadmin = false`. El rol solo se otorga con
`python -m app.cli create-admin` dentro del contenedor, para que nadie escale
privilegios desde la interfaz. El reverso es que el sistema puede quedarse sin
administrador si se pierde esa cuenta: por eso el backend impide eliminar o
desactivar al último superadministrador activo, y que uno se quite a sí mismo.

**La sesión de captura por QR es la credencial, durante diez minutos.** Los
dos endpoints de `/api/publico/recepcion/*` son públicos porque el celular que
toma la foto no inició sesión en el panel. Lo que los sostiene son tres cosas
**a la vez**: el identificador de sesión es un UUID que no se adivina, expira a
los diez minutos y solo admite una subida (`pendiente → subida → usada`).
Quitar cualquiera de las tres deja el hueco abierto. El peor caso es que quien
intercepte el código en esa ventana suba una foto que el operador vería en
pantalla antes de guardar nada.

**El texto de la remisión sale hacia el servidor de Ollama.** La foto **no**:
al modelo solo se le manda el texto que Tesseract ya leyó. Aun así, ese texto
viaja en claro por la LAN hasta `192.168.1.56`. Es una máquina de la propia
red y no sale a internet, pero si algún día el host de Ollama se mueve fuera
del edificio, esa decisión hay que volver a tomarla: son datos de proveedores
y cantidades compradas.

**La foto de la remisión se guarda siempre, aunque no se guarde la
recepción.** Es deliberado: la evidencia es lo primero que se persiste, antes
de intentar leerla. La consecuencia es que `recepciones_fotos` acumula fotos
huérfanas de capturas que el operador abandonó. No hay limpieza automática; si
llega a pesar, se borran las que no tengan `recepcion` ni sesión asociada.

**El secreto del webhook de rondines es la credencial, y puede fabricar
historia.** Quien lo tenga puede inyectar visitas **en cualquier punto y con
cualquier hora pasada**. Es estrictamente más poder que el QR pegado en la
pared al que sustituye, que solo podía falsificar «ahora».

Tres cosas acotan el riesgo, y ninguna lo elimina:

- `recibido_at` guarda el reloj del servidor junto a `escaneado_at`, que lo
  dicta AppSheet. La diferencia entre las dos es lo único que distingue una
  sincronización tardía —normal: la app captura sin señal— de una hora
  fabricada. Un escaneo que dice 03:00 y llegó a las 09:00 puede ser cualquiera
  de las dos; lo que lo delata es compararlo con el patrón del resto del turno.
- Sin `RONDINES_WEBHOOK_SECRETO` capturado, el endpoint responde **503**. Un
  despliegue a medio configurar no queda abierto.
- **Rotarlo es trivial**: se cambia en el `.env`, se reinicia el backend y se
  actualiza la cabecera del Bot. Ésa es la mejora real sobre el QR viejo, que
  era irrotable sin reimprimir y volver a pegar 44 etiquetas.

**El escaneo sigue sin identificar al guardia.** AppSheet manda
`Email_Guardia` (`USEREMAIL()`) y se guarda, pero en la práctica es una cuenta
compartida de turno: medido sobre el histórico, 49,441 de 49,488 escaneos
traen el mismo correo. La bitácora no puede decir quién fue, igual que antes.
El control real sigue siendo de supervisión, no técnico. Si algún día importa,
la salida es darle su cuenta a cada guardia en AppSheet.

**El GPS no sirve para verificar presencia**, aunque venga en el 100 % de los
escaneos. Es `=HERE()`, el GPS del celular: medido contra las coordenadas de
referencia de cada punto, la mediana del error son 94 m y solo el 23.7 % cae
dentro de 50 m, mientras que los 44 puntos de la planta están más juntos que
eso. Se guarda como evidencia; un semáforo de «el guardia no estuvo ahí»
construido sobre este dato acusaría en falso.

**AppSheet es ahora la fuente de verdad de los rondines.** Su control de
acceso, su retención y quién puede editar sus filas quedan fuera de este
perímetro y no los audita nadie desde aquí. Alguien con permiso de edición en
la app puede cambiar la hora de un escaneo ya capturado, y aquí llegaría como
un registro más.

**La liga del cuestionario es la credencial.** Quien tenga el token puede
contestar, y puede pasárselo a alguien de fuera. No hay forma de distinguirlos:
el nombre y el número de empleado se teclean, no se verifican contra nómina. Es
el modelo original de la especificación y se mantuvo así porque emitir un token
por persona obligaría a repartir 500 ligas distintas en vez de pegar un QR en
cada área. La consecuencia práctica: los resultados sirven para medir
conocimiento del grupo, no para acreditar formalmente a un individuo.

**Un token filtrado no se puede rotar sin invalidar los QR impresos.**
Desactivar el cuestionario desde el panel lo cierra para todos.

**La regla de intento único se apoya en el número de empleado.** Quien teclee
uno distinto puede contestar otra vez.

**El límite de tasa es aproximado.** Vive en la memoria de cada worker y se
reinicia con el contenedor. Contiene abuso automatizado; no es una cuota
exacta.
