# Permisos de energía para Raspberry Pi

`signage-app` ejecuta únicamente los comandos de reinicio y apagado mediante
`systemctl`. Instala la regla restringida con:

```bash
sudo install -o root -g root -m 0440 \
  deploy/rodall-power.sudoers \
  /etc/sudoers.d/rodall-power
sudo visudo -cf /etc/sudoers.d/rodall-power
```

El resultado de la validación debe indicar:

```text
/etc/sudoers.d/rodall-power: parsed OK
```

La regla no concede acceso general a `sudo`; solo autoriza al usuario
`rodall` a ejecutar `/usr/bin/systemctl reboot` y
`/usr/bin/systemctl poweroff` sin una terminal interactiva.
