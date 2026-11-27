from django.apps import AppConfig


class ShowcasesConfig(AppConfig):
    name = "showcases"
    verbose_name = "Showcases"

    def ready(self) -> None:
        from . import signals  # noqa: F401
