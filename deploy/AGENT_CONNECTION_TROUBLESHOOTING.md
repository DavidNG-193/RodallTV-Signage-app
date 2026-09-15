# Recuperación de conexión del agente RodallTV

Esta guía sirve para el escenario donde la Raspberry no se conecta o no
sincroniza contenido después de cambiar la dirección del servidor, iniciar una
nueva base de datos Docker o modificar las credenciales del dispositivo.
En la instalacion de produccion HTTP, usar `rodalltv.rodall`, que debe resolver
a `10.11.20.40` desde la Raspberry.

## 1. Comprobar la conectividad básica

Desde la Raspberry, consulta el health check del servidor:

```bash
getent hosts rodalltv.rodall
curl http://rodalltv.rodall:8080/health/ready
```

La respuesta esperada es:

```text
Healthy
```

Si no responde, verifica que:

- la Raspberry y el servidor estén en la misma red;
- Docker Compose esté iniciado;
- `web`, `api` y `db` aparezcan como `healthy`;
- el firewall del servidor permita conexiones TCP al puerto `8080`;
- la dirección IP del servidor no haya cambiado.

En el servidor se puede consultar el estado con:

```bash
sudo docker compose ps --all
```

## 2. Modificar el archivo de configuración correcto

Cuando el agente se ejecuta mediante `systemd`, su configuración oficial es:

```text
/etc/rodalltv/signage.env
```

El archivo `.env` dentro del repositorio se utiliza para ejecuciones manuales,
pero no sustituye las variables que `systemd` ya inyectó al proceso.

Edita el archivo oficial:

```bash
sudo nano /etc/rodalltv/signage.env
```

Comprueba que tenga la dirección y las credenciales vigentes:

```env
RODALL_API_BASE_URL=http://rodalltv.rodall:8080
RODALL_DEVICE_ID=ID_DEL_DISPOSITIVO
RODALL_DEVICE_TOKEN=TOKEN_DEL_DISPOSITIVO
```

No agregues `/api` al final de `RODALL_API_BASE_URL`. El agente añade las rutas
de la API automáticamente.

Protege el archivo, ya que contiene el token del dispositivo:

```bash
sudo chown root:rodall /etc/rodalltv/signage.env
sudo chmod 640 /etc/rodalltv/signage.env
```

## 3. Reiniciar el agente

Las variables se leen al iniciar el proceso. Después de cambiar el archivo,
reinicia el servicio:

```bash
sudo systemctl restart rodall-signage.service
sudo systemctl status rodall-signage.service
```

No es necesario ejecutar `systemctl daemon-reload` cuando solo cambió
`signage.env`. Se necesita únicamente si se modificó el archivo `.service`.

## 4. Confirmar la configuración efectiva

Comprueba la URL que recibió realmente el proceso en ejecución:

```bash
pid=$(systemctl show -p MainPID --value rodall-signage.service)

sudo sh -c "tr '\0' '\n' < /proc/$pid/environ" |
  grep '^RODALL_API_BASE_URL='
```

Debe mostrar la dirección y el puerto actuales. Si muestra un valor anterior,
revisa la definición del servicio:

```bash
sudo systemctl show rodall-signage.service \
  -p Environment \
  -p EnvironmentFiles \
  -p ExecStart

sudo systemctl cat rodall-signage.service
```

Busca variables antiguas definidas directamente mediante `Environment=` o un
`EnvironmentFile` diferente.

## 5. Probar la autenticación del dispositivo

El endpoint de salud no valida el ID ni el token. Realiza una prueba autenticada
desde la Raspberry:

```bash
curl -i -X POST \
  "http://IP_O_DOMINIO_DEL_SERVIDOR:8080/api/agent/heartbeat" \
  -H "X-Device-Id: ID_DEL_DISPOSITIVO" \
  -H "X-Device-Token: TOKEN_DEL_DISPOSITIVO" \
  -H "Content-Type: application/json" \
  -d '{"agentVersion":"manual-test"}'
```

Interpretación:

- `200 OK`: la red, URL e identidad del dispositivo son correctas;
- `401 Unauthorized`: el ID o token no pertenecen a la base actual;
- `404 Not Found`: la URL o ruta es incorrecta;
- timeout o conexión rechazada: revisa red, puerto y firewall.

Si Docker inició con una base vacía, registra un dispositivo nuevo desde el
panel administrativo y copia el nuevo ID y token a `signage.env`. Para conservar
las credenciales existentes, restaura la base anterior en el volumen Docker.

## 6. Diagnosticar la sincronización multimedia

Primero verifica que el dispositivo tenga una playlist asignada:

```bash
curl -s \
  "http://IP_O_DOMINIO_DEL_SERVIDOR:8080/api/agent/assignment" \
  -H "X-Device-Id: ID_DEL_DISPOSITIVO" \
  -H "X-Device-Token: TOKEN_DEL_DISPOSITIVO" |
  python3 -m json.tool
```

`hasAssignment` debe ser `true`.

Después consulta el manifiesto:

```bash
curl -s \
  "http://IP_O_DOMINIO_DEL_SERVIDOR:8080/api/agent/manifest" \
  -H "X-Device-Id: ID_DEL_DISPOSITIVO" \
  -H "X-Device-Token: TOKEN_DEL_DISPOSITIVO" |
  python3 -m json.tool
```

Cada `downloadUrl` debe contener el dominio o IP correctos y el puerto `8080`
cuando se utilice HTTP local. Por ejemplo:

```text
http://rodalltv.rodall:8080/api/agent/media/ID/download
```

Si falta `:8080`, confirma que Nginx use `$http_host` en los encabezados `Host`
y `X-Forwarded-Host`, reconstruye `web` y vuelve a consultar el manifiesto:

```powershell
docker compose up -d --build web
```

Si el manifiesto responde `409 Conflict`, comprueba que todos los archivos de la
playlist estén activos y existan en el volumen multimedia de Docker.

## 7. Revisar los logs nuevos

En la Raspberry:

```bash
sudo journalctl -u rodall-signage.service -n 100 --no-pager
tail -n 100 /home/rodall/RodallTV/signage-app/runtime/logs/rodall-signage.log
```

Para observar nuevos intentos en tiempo real:

```bash
tail -f /home/rodall/RodallTV/signage-app/runtime/logs/rodall-signage.log
```

Busca mensajes como `Heartbeat fallido`, `Falló la sincronización`, `401`,
`Connection refused` o `timed out`. Verifica siempre la fecha del mensaje para
no confundir un error antiguo con el estado actual.

## 8. Evitar que vuelva a ocurrir

- Reserva la IP del servidor mediante DHCP o utiliza un nombre DNS estable.
- Mantén `/etc/rodalltv/signage.env` como única configuración de producción.
- Reinicia el servicio después de cambiar variables.
- No elimines el volumen `rodalltv_db_data`; contiene dispositivos y tokens.
- No elimines `rodalltv_media_data`; contiene los archivos multimedia.
- Evita `docker compose down -v`, porque elimina ambos volúmenes.
- Guarda respaldos de PostgreSQL y del almacenamiento multimedia.
- Nunca publiques ni copies el token del agente en logs, commits o capturas.

Detener y volver a iniciar sin borrar datos es seguro:

```powershell
docker compose down
docker compose up -d
```
