# Despliegue en el servidor de producción

Guía paso a paso para alojar el sistema en un servidor Ubuntu, clonando desde
GitHub por SSH.

Los pasos están marcados según dónde se ejecutan:

- **[LOCAL]** — en esta máquina, la de desarrollo.
- **[SERVIDOR]** — en el servidor Ubuntu de planta, por SSH.

---

## Antes de empezar

Ten a la mano:

- Acceso SSH al servidor con un usuario que pueda usar `sudo`.
- La IP del servidor en la LAN. **Debería ser fija**: si el DHCP se la cambia,
  todos los códigos QR impresos dejan de funcionar.
- Tu cuenta de GitHub con acceso al repositorio `Jarsen-dev/security_evaluations`.

---

# Parte 1 — En tu máquina de desarrollo

## Paso 1 [LOCAL] · Confirmar que no se sube nada sensible

El `.env` tiene la contraseña de la base de datos y la llave de firma. **Nunca
debe llegar a GitHub.** Verifícalo antes del commit:

```bash
cd /home/jarsen/security_evaluations
git status --short | grep -E '^\S+\s+\.env$' && echo "PELIGRO: .env está en el índice" || echo "OK: .env fuera del índice"
git diff --cached --name-only | grep -E 'node_modules|\.next/|\.sql\.gz' || echo "OK: sin basura"
```

Ambas líneas deben decir OK.

## Paso 2 [LOCAL] · Commit y push

Los 107 archivos ya están preparados en el índice, pero **todavía no hay
commit**:

```bash
git commit -m "feat: sistema de evaluación de conocimientos completo (fases 1-8)"
git push origin main
```

Confirma que llegó:

```bash
git log origin/main --oneline | head -3
```

---

# Parte 2 — En el servidor Ubuntu

## Paso 3 [SERVIDOR] · Conectarte

```bash
ssh usuario@192.168.1.X
```

## Paso 4 [SERVIDOR] · Instalar Docker y Docker Compose

Si el servidor ya los tiene, salta al paso 5. Verifica con
`docker --version && docker compose version`.

```bash
sudo apt update
sudo apt install -y ca-certificates curl git

# Repositorio oficial de Docker
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

Para usar Docker sin `sudo`:

```bash
sudo usermod -aG docker $USER
newgrp docker          # o cierra la sesión SSH y vuelve a entrar
docker ps              # debe funcionar sin sudo
```

> **Nota sobre el comando.** Si tu servidor trae el plugin, usarás
> `docker compose` (con espacio). Si trae el binario viejo, será
> `docker-compose` (con guion). Comprueba cuál tienes y **usa ese en todos los
> comandos siguientes**. Verifica con:
> `docker compose version || docker-compose version`

## Paso 5 [SERVIDOR] · Llave SSH para GitHub

Genera una llave en el servidor:

```bash
ssh-keygen -t ed25519 -C "servidor-planta" -f ~/.ssh/id_ed25519 -N ""
cat ~/.ssh/id_ed25519.pub
```

Copia lo que imprime y dalo de alta en GitHub. Lo más seguro es una **deploy
key de solo lectura**, no tu llave personal:

1. Ve a `https://github.com/Jarsen-dev/security_evaluations/settings/keys`
2. **Add deploy key** → pega la llave → nombre: `servidor-planta`
3. **No** marques "Allow write access".

Prueba la conexión:

```bash
ssh -T git@github.com
```

Debe responder `Hi Jarsen-dev/security_evaluations! You've successfully
authenticated...`. La primera vez pregunta si confías en el host: responde
`yes`.

## Paso 6 [SERVIDOR] · Clonar el repositorio

```bash
sudo mkdir -p /opt/evaluaciones
sudo chown $USER:$USER /opt/evaluaciones
git clone git@github.com:Jarsen-dev/security_evaluations.git /opt/evaluaciones
cd /opt/evaluaciones
```

## Paso 7 [SERVIDOR] · Verificar que los puertos estén libres

```bash
ss -tulpn | grep -E ':(8080|3200|8200|5442) ' || echo "OK: los 4 puertos están libres"
```

En producción solo se publica el **8080**. Si está ocupado, cambia
`NGINX_PORT` en el `.env` del paso siguiente y usa ese puerto en todas las URLs.

## Paso 8 [SERVIDOR] · Averiguar la IP del servidor

```bash
hostname -I | awk '{print $1}'
```

Anótala. Si no es fija, fíjala antes de continuar (por reserva DHCP en el
router o con netplan). **Si la IP cambia después, todos los QR impresos quedan
inservibles.**

## Paso 9 [SERVIDOR] · Crear el archivo de configuración

Este es el paso donde más se equivoca la gente. Léelo completo.

```bash
cp .env.example .env
```

Genera los dos secretos:

```bash
# Llave de firma de las sesiones
python3 -c "import secrets; print(secrets.token_urlsafe(48))"

# Contraseña de la base de datos
python3 -c "import secrets; print(secrets.token_urlsafe(18))"
```

Edita el archivo:

```bash
nano .env
```

Cambia **estas cuatro cosas**:

| Variable | Valor |
|---|---|
| `SECRET_KEY` | la primera llave generada |
| `POSTGRES_PASSWORD` | la segunda |
| `DATABASE_URL` | la misma contraseña, dentro de la URL |
| `NEXT_PUBLIC_BASE_URL` | `http://<IP-del-paso-8>:8080` |

Ejemplo con IP `192.168.1.50`:

```
SECRET_KEY=xK9pQ2mN7vR4tY8wZ1aB3cD5eF6gH0jL2kM4nP7qS9uV
POSTGRES_PASSWORD=Tr7nQ2xWm9LpKd4Zc8
DATABASE_URL=postgresql+asyncpg://evaluaciones:Tr7nQ2xWm9LpKd4Zc8@db:5432/evaluaciones
NEXT_PUBLIC_BASE_URL=http://192.168.1.50:8080
```

Deja `COOKIE_SECURE=false`: la LAN va por HTTP y con `true` el navegador
descarta la cookie de sesión y el login nunca funciona.

Verifica que la contraseña coincida en los dos lugares:

```bash
grep -E '^(POSTGRES_PASSWORD|DATABASE_URL|NEXT_PUBLIC_BASE_URL)=' .env
```

> **Trampa importante:** `NEXT_PUBLIC_BASE_URL` se incrusta en el frontend
> **durante la compilación**. Si la cambias más adelante, no basta reiniciar:
> hay que reconstruir con `docker compose up -d --build frontend`.

## Paso 10 [SERVIDOR] · Levantar el sistema

```bash
docker compose up -d --build
```

La primera vez tarda varios minutos: compila el backend y el frontend. Las
migraciones de la base de datos se aplican solas al arrancar.

Verifica:

```bash
docker compose ps
```

Los cuatro servicios deben estar `Up`, y `evaluaciones_db` marcado `healthy`.

```bash
curl http://localhost:8080/api/health
```

Debe responder `{"status":"ok","db":"ok","version":"0.1.0"}`.

## Paso 11 [SERVIDOR] · Crear el usuario administrador

```bash
docker compose exec backend python -m app.cli create-admin --username admin
```

Pide la contraseña por teclado, dos veces, sin mostrarla. Mínimo 8 caracteres.
**Usa una contraseña real, no `admin123`.**

## Paso 12 [SERVIDOR] · Abrir el puerto en el firewall

Si el servidor usa `ufw`:

```bash
sudo ufw status
sudo ufw allow 8080/tcp comment 'Evaluaciones'
sudo ufw reload
```

Si `ufw` está inactivo, no hace falta.

## Paso 13 [SERVIDOR] · Verificación de punta a punta

Desde el servidor:

```bash
curl -s http://localhost:8080/api/health
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8080/login    # 200
```

Desde **otra máquina de la LAN**, en el navegador:

```
http://<IP-del-servidor>:8080/login
```

Entra con el usuario que creaste. Luego, la prueba que de verdad importa:

1. Crea un cuestionario de prueba con 2 preguntas.
2. Abre su **QR** y confirma que la URL dice la IP del servidor, no `localhost`.
3. **Escanéalo con un celular conectado a la WiFi de planta** y contesta.

Si el celular no abre la liga, revisa en este orden: que esté en la misma red,
que el firewall permita el 8080, y que `NEXT_PUBLIC_BASE_URL` tenga la IP
correcta.

## Paso 14 [SERVIDOR] · Programar los respaldos

```bash
chmod +x scripts/backup.sh
./scripts/backup.sh              # probar que funciona
ls -lh backups/
```

Progámalo todos los días a las 2 de la mañana:

```bash
crontab -e
```

Agrega:

```
0 2 * * * /opt/evaluaciones/scripts/backup.sh >> /var/log/evaluaciones_backup.log 2>&1
```

Los respaldos se guardan en `/opt/evaluaciones/backups/` con 30 días de
retención. **Cópialos fuera del servidor con regularidad**: un disco dañado se
lleva la base y sus respaldos juntos.

---

# Parte 3 — Operación

## Actualizar desde GitHub

```bash
cd /opt/evaluaciones
./scripts/backup.sh                      # respaldo antes de nada
git pull
docker compose up -d --build             # las migraciones corren solas
docker compose logs backend | tail -20   # confirmar que arrancó
```

`.env` no viaja por git. Si la actualización trae variables nuevas, compáralo
con `.env.example` y captúralas antes de reconstruir:

```bash
diff <(grep -oE '^[A-Z_]+' .env.example | sort) <(grep -oE '^[A-Z_]+' .env | sort)
```

El sistema está publicado en internet por el túnel de Cloudflare: antes de
abrir una campaña nueva, revisa la lista de `SEGURIDAD.md`.

## Comandos frecuentes

```bash
docker compose ps                        # estado
docker compose logs -f backend           # seguir logs
docker compose restart backend           # reiniciar un servicio
docker compose down                      # detener (los datos se conservan)
```

`docker compose down -v` **borra la base de datos**. No lo uses salvo que
quieras empezar de cero.

## Administradores

```bash
docker compose exec backend python -m app.cli listar-admins
docker compose exec backend python -m app.cli create-admin --username otro
docker compose exec backend python -m app.cli create-admin --username admin --reestablecer
```

## Restaurar un respaldo

```bash
gunzip -c backups/evaluaciones_20260817_020000.sql.gz | \
  docker exec -i evaluaciones_db psql -U evaluaciones -d evaluaciones
```

---

## Lista de verificación final

- [ ] `.env` existe en el servidor y **no** está en GitHub
- [ ] `SECRET_KEY` y `POSTGRES_PASSWORD` son valores propios, no los de ejemplo
- [ ] `DATABASE_URL` lleva la misma contraseña que `POSTGRES_PASSWORD`
- [ ] `NEXT_PUBLIC_BASE_URL` tiene la IP real del servidor y el puerto 8080
- [ ] La IP del servidor es fija
- [ ] `COOKIE_SECURE=false`
- [ ] Los 4 servicios `Up`, `db` en `healthy`
- [ ] `/api/health` responde `db: ok`
- [ ] Puerto 8080 abierto en el firewall
- [ ] Admin creado con contraseña propia
- [ ] QR probado **desde un celular real** en la WiFi de planta
- [ ] Respaldo ejecutado a mano y cron programado
- [ ] Datos de demostración borrados (si clonaste con ellos)

---

## Problemas comunes

**El QR no abre desde el celular.**
`NEXT_PUBLIC_BASE_URL` tiene `localhost` o una IP equivocada. Corrígela y
reconstruye: `docker compose up -d --build frontend`. Reiniciar no basta.

**"Estás enviando demasiadas peticiones" durante una evaluación masiva.**
El límite es 30 peticiones por minuto y por IP. Si la WiFi de planta hace NAT,
todos los celulares llegan con la misma IP y se bloquean entre sí. Sube
`RATE_LIMIT_PETICIONES` en el `.env` y reinicia el backend.

**El login no funciona.**
Confirma que entras por el puerto 8080 y que `COOKIE_SECURE=false`.

**El backend no arranca.**
`docker compose logs backend`. Casi siempre es que `DATABASE_URL` no coincide
con `POSTGRES_PASSWORD`.

**`git pull` pide contraseña.**
La deploy key no quedó bien. Prueba `ssh -T git@github.com` y revisa que el
remoto sea SSH: `git remote -v` debe decir `git@github.com:...`, no `https://`.
