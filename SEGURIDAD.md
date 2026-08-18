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
| `/login`, `/cuestionarios`, `/estadisticas` | Solo administradores |
| `/api/auth/*`, `/api/cuestionarios/*`, `/api/preguntas/*`, `/api/estadisticas/*`, `/api/metas-area`, `/api/wifi` | Solo administradores |

`/api/wifi` devuelve la contraseña de la red en claro; exige sesión por eso.

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
| Panel — estadísticas | `evaluaciones.chwon.it.com` | `estadisticas` |
| API — auth | `evaluaciones.chwon.it.com` | `api/auth` |
| API — cuestionarios | `evaluaciones.chwon.it.com` | `api/cuestionarios` |
| API — preguntas | `evaluaciones.chwon.it.com` | `api/preguntas` |
| API — estadísticas | `evaluaciones.chwon.it.com` | `api/estadisticas` |
| API — metas | `evaluaciones.chwon.it.com` | `api/metas-area` |
| API — wifi | `evaluaciones.chwon.it.com` | `api/wifi` |

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
- [ ] Aplicaciones de Access creadas y verificadas con los `curl` de arriba.
- [ ] `/r/<token>` abre sin pedir nada desde una red externa.
- [ ] `NEXT_PUBLIC_BASE_URL` es el dominio y el frontend se reconstruyó después
      de cambiarlo (Next incrusta esa variable en el build, no la lee en
      runtime).
- [ ] Un cuestionario contestado de punta a punta desde datos móviles.

---

## 5. Vigilancia durante la campaña

```bash
# Intentos de acceso fallidos
docker compose logs backend | grep -E "Contraseña incorrecta|usuario inexistente"

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
