# Despliegue del agente en Raspberry Pi desde cero

Esta guía instala RodallTV Signage en una Raspberry Pi dedicada y lo deja
arrancando automáticamente a pantalla completa. Los comandos asumen:

- Raspberry Pi 4 o 5 con Raspberry Pi OS de 64 bits **con escritorio**.
- Un usuario local llamado `USUARIO`.
- El repositorio clonado en `/home/USUARIO/RodallTV/signage-app`.
- Una pantalla conectada por HDMI.
- Acceso de red al backend de RodallTV.

> No copies un token real al repositorio. El ID y el token del dispositivo se
> guardan únicamente en `/etc/rodalltv/signage.env`.

## 1. Preparar la Raspberry Pi

Graba Raspberry Pi OS de 64 bits con escritorio mediante Raspberry Pi Imager.
En las opciones avanzadas configura el usuario `USUARIO`, la red, la zona
horaria y SSH si administrarás el equipo de forma remota.

Después del primer arranque, abre una terminal y actualiza el sistema:

```bash
sudo apt update
sudo apt full-upgrade -y
sudo reboot
```

La integración de `mpv` dentro de la ventana Qt utiliza X11. Ejecuta:

```bash
sudo raspi-config
```

En el menú activa el inicio automático al escritorio para `rodall` y selecciona
X11 como compositor, no Wayland. Los nombres exactos de las opciones pueden
cambiar entre versiones de Raspberry Pi OS. Reinicia al terminar y verifica:

```bash
echo "$XDG_SESSION_TYPE"
```

El resultado esperado es `x11`.

## 2. Instalar dependencias del sistema

```bash
sudo apt install -y \
  git git-lfs mpv python3 python3-pip python3-venv \
  libegl1 libgl1 libxkbcommon-x11-0 libxcb-cursor0 \
  ca-certificates curl
git lfs install
```

Comprueba que `mpv` y Python estén disponibles:

```bash
python3 --version
mpv --version
```

## 3. Descargar e instalar el agente

```bash
cd /home/USUARIO/RodallTV
git clone https://github.com/DavidNG-193/signage-app.git
cd signage-app
git lfs pull
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements-dev.txt
mkdir -p runtime/cache runtime/content runtime/logs
```

Si el repositorio es privado, configura primero una llave SSH de solo lectura o
un token de acceso de GitHub y usa la URL autorizada que corresponda. No guardes
ese token en el archivo de configuración del agente.

## 4. Registrar el dispositivo en RodallTV

En el panel administrativo crea o registra la pantalla. Conserva los dos datos
que entrega el panel:

- ID del dispositivo (`RODALL_DEVICE_ID`).
- Token del dispositivo (`RODALL_DEVICE_TOKEN`).

La URL base debe apuntar al servidor RodallTV y **no** debe terminar en `/api`.
Desde la Raspberry verifica primero que el backend responda:

```bash
curl -I http://IP_O_DOMINIO_DEL_SERVIDOR:8080/
```

## 5. Crear la configuración de producción

```bash
sudo install -d -o root -g rodall -m 0750 /etc/rodalltv
sudo nano /etc/rodalltv/signage.env
```

Pega y completa lo siguiente:

```ini
RODALL_APP_ENV=production
RODALL_MPV_PATH=/usr/bin/mpv
RODALL_MPV_HWDEC=auto-safe
RODALL_MPV_PROFILE=fast
RODALL_MPV_GPU_DUMB_MODE=true
RODALL_LOG_LEVEL=INFO
RODALL_WINDOWED=false
RODALL_TEST_MEDIA=
RODALL_IPC_NAME=rodalltv-mpv
RODALL_API_BASE_URL=http://IP_O_DOMINIO_DEL_SERVIDOR:8080
RODALL_DEVICE_ID=ID_DEL_DISPOSITIVO
RODALL_DEVICE_TOKEN=TOKEN_DEL_DISPOSITIVO
RODALL_HEARTBEAT_SECONDS=30
RODALL_SYNC_SECONDS=60
RODALL_EXCHANGE_RATE_SECONDS=900
RODALL_WEATHER_SECONDS=900
RODALL_REFERENCE_SECONDS=60
```

## 6. Autorizar reinicio y apagado remotos

El agente solo necesita permiso para las dos acciones declaradas en la regla:

```bash
cd /home/USUARIO/RodallTV/signage-app
sudo install -o root -g root -m 0440 \
  deploy/rodall-power.sudoers \
  /etc/sudoers.d/rodall-power
sudo visudo -cf /etc/sudoers.d/rodall-power
```

La validación debe terminar con `parsed OK`.

## 7. Instalar el servicio de inicio automático

Crea el servicio:

```bash
sudo nano /etc/systemd/system/rodall-signage.service
```

Contenido:

```ini
[Unit]
Description=RodallTV Signage Agent
Wants=network-online.target
After=network-online.target display-manager.service

[Service]
Type=simple
User=rodall
Group=rodall
WorkingDirectory=/home/USUARIO/RodallTV/signage-app
EnvironmentFile=/etc/rodalltv/signage.env
Environment=DISPLAY=:0
Environment=XAUTHORITY=/home/USUARIO/RodallTV/.Xauthority
Environment=QT_QPA_PLATFORM=xcb
ExecStart=/home/USUARIO/RodallTV/signage-app/.venv/bin/python /home/USUARIO/RodallTV/signage-app/main.py
Restart=always
RestartSec=5
TimeoutStopSec=15

[Install]
WantedBy=graphical.target
```

Actívalo:

```bash
sudo systemctl daemon-reload
sudo systemctl enable rodall-signage.service
sudo reboot
```

Después de que aparezca el escritorio, revisa el estado:

```bash
sudo systemctl status rodall-signage.service --no-pager
sudo journalctl -u rodall-signage.service -n 100 --no-pager
tail -n 100 /home/USUARIO/RodallTV/signage-app/runtime/logs/rodall-signage.log
```

La aplicación debe ocupar la pantalla completa, registrar el heartbeat y
descargar el manifiesto y el contenido asignados.

## 8. Evitar suspensión y pantalla negra

En la configuración del escritorio desactiva el protector de pantalla, el
bloqueo y el apagado automático del monitor. Para comprobarlo temporalmente en
una sesión X11:

```bash
xset s off
xset -dpms
xset s noblank
```

Conviene aplicar estas opciones desde el inicio automático del escritorio para
que se restauren después de cada reinicio.

## 9. Actualizar el agente

```bash
sudo systemctl stop rodall-signage.service
cd /home/USUARIO/RodallTV/signage-app
git pull --ff-only
git lfs pull
.venv/bin/python -m pip install -r requirements-dev.txt
sudo systemctl start rodall-signage.service
sudo systemctl status rodall-signage.service --no-pager
```

## Diagnóstico rápido

- `could not connect to display`: confirma inicio de sesión gráfico, X11,
  `DISPLAY=:0` y la existencia de `/home/rodall/.Xauthority`.
- `mpv todavía no está listo`: ejecuta `mpv --version` y revisa el log del
  agente para conocer el error de video o IPC.
- Sin contenido: valida URL, ID y token en `/etc/rodalltv/signage.env` y revisa
  la asignación del dispositivo en el panel.
- Sin conexión al backend: prueba desde la Raspberry el hostname y puerto con
  `curl`; no agregues `/api` a `RODALL_API_BASE_URL`.
- Para un diagnóstico completo consulta
  `deploy/AGENT_CONNECTION_TROUBLESHOOTING.md`.
