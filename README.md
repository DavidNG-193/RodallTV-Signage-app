# RodallTV Signage

Agente de señalización digital de RodallTV para Raspberry Pi y Windows. La
aplicación sincroniza la asignación y el contenido del dispositivo con el
backend, reproduce imágenes y video mediante `mpv`, y mantiene una caché local
para continuar operando durante interrupciones de red.

## Raspberry Pi

Consulta la guía completa de instalación, configuración y operación:

- [Despliegue en Raspberry Pi desde cero](deploy/RASPBERRY_PI_DESDE_CERO.md)
- [Diagnóstico de conexión del agente](deploy/AGENT_CONNECTION_TROUBLESHOOTING.md)

## Desarrollo local

```bash
python -m venv .venv
python -m pip install -r requirements-dev.txt
python main.py --windowed
```

La configuración parte de `.env.example`. Copia ese archivo como `.env` y no
versiones las credenciales reales del dispositivo.
