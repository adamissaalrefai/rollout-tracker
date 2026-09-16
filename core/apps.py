from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self):
        # Registers the email-notification signal from signals.py.
        # Signals do nothing until this import happens — Django won't
        # discover signals.py on its own.
        import core.signals  # noqa: F401