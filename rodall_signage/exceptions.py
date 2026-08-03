class RodallSignageError(Exception):
    """Excepción base controlada de la aplicación."""


class ConfigurationError(RodallSignageError):
    """Error en una configuración requerida."""


class PlayerError(RodallSignageError):
    """Error controlado del reproductor."""


class LifecycleError(RodallSignageError):
    """Error durante el inicio o cierre."""