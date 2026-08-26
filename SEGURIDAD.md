# Seguridad y exposición pública

El sistema dejó de ser una aplicación de LAN: un túnel de Cloudflare lo publica
en `https://evaluaciones.chwon.it.com` para que los ~500 empleados contesten con
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
| `/administracion` | Solo el superadministrador |
| `/api/auth/*`, `/api/cuestionarios/*`, `/api/preguntas/*`, `/api/estadisticas/*`, `/api/metas-area`, `/api/wifi`, `/api/controles/*` | Solo usuarios del panel, según sus permisos |
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
un JSON por módulo (`cuestionarios`, `controles`, `inventario`): **estar
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
| Panel — login | `evaluaciones.chwon.it.com` | `login` |
| Panel — cuestionarios | `evaluaciones.chwon.it.com` | `cuestionarios` |
| Panel — controles | `evaluaciones.chwon.it.com` | `controles` |
| Panel — inventario | `evaluaciones.chwon.it.com` | `inventario` |
| API — auth | `evaluaciones.chwon.it.com` | `api/auth` |
| API — cuestionarios | `evaluaciones.chwon.it.com` | `api/cuestionarios` |
| API — preguntas | `evaluaciones.chwon.it.com` | `api/preguntas` |
| API — estadísticas | `evaluaciones.chwon.it.com` | `api/estadisticas` |
| API — metas | `evaluaciones.chwon.it.com` | `api/metas-area` |
| API — wifi | `evaluaciones.chwon.it.com` | `api/wifi` |
| API — controles | `evaluaciones.chwon.it.com` | `api/controles` |
| Panel — estudios | `evaluaciones.chwon.it.com` | `estudios` |
| API — estudios | `evaluaciones.chwon.it.com` | `api/estudios` |
| Panel — administración | `evaluaciones.chwon.it.com` | `administracion` |
| API — administración | `evaluaciones.chwon.it.com` | `api/administracion` |

> **Pendiente.** Siete aplicaciones son nuevas y **todavía no están dadas de
> alta**: `controles`, `inventario`, `api/controles`, `estudios`,
> `api/estudios`, `administracion` y `api/administracion`. Mientras no se
> creen, esas rutas quedan fuera de Access
> y lo único que las defiende es la cookie de sesión más la comprobación de
> permisos: la pantalla de login del panel no aparece, pero la ruta sí es
> alcanzable desde internet. Las dos de administración son las más sensibles de
> la lista, porque desde ahí se dan de alta usuarios.
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
/api/publico/  → lo que el formulario consume
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
curl -sI https://evaluaciones.chwon.it.com/login | head -1
curl -sI https://evaluaciones.chwon.it.com/api/estadisticas/resumen | head -1

# Debe seguir funcionando sin pedir nada
curl -s  https://evaluaciones.chwon.it.com/api/health
curl -sI https://evaluaciones.chwon.it.com/r/<token-de-un-cuestionario> | head -1
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
curl -s  https://evaluaciones.chwon.it.com/api/health          # {"status":"ok","db":"ok"}
curl -sI https://evaluaciones.chwon.it.com/api/docs | head -1  # 404
curl -sI https://evaluaciones.chwon.it.com/ | grep -i strict-transport-security
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
      **incluidas las nuevas** de `controles`, `inventario`, `api/controles`,
      `administracion` y `api/administracion`.
- [ ] `/r/<token>` abre sin pedir nada desde una red externa.
- [ ] `NEXT_PUBLIC_BASE_URL` es el dominio y el frontend se reconstruyó después
      de cambiarlo (Next incrusta esa variable en el build, no la lee en
      runtime).
- [ ] Un cuestionario contestado de punta a punta desde datos móviles.

---

## 5. Vigilancia durante la campaña

La bitácora del panel (**Administración → Logs**) es ahora la primera parada:
filtra por fecha, hora y usuario sin entrar al servidor. Lo de abajo sigue
sirviendo para lo que la bitácora no cubre.

```bash
# Intentos de acceso fallidos (también salen en la bitácora, como sesion.fallida)
docker compose logs backend | grep -E "Contraseña incorrecta|usuario inexistente|cuenta desactivada"

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
