# -*- encoding: utf-8 -*-
import asyncio as aio
import threading
from django.apps import AppConfig


class RaceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "race"

    def ready(self):
        import race.signals

        if threading.current_thread() == threading.main_thread():
            from .scheduler import racing_start
            racing_start()
