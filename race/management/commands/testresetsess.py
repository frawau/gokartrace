import datetime as dt
import random
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth.models import Group
from django.core.validators import MinValueValidator, MaxValueValidator
from race.models import (
    Session,
    )


class Command(BaseCommand):
    help = "Creates a championship, rounds, teams, and team members."

    def handle(self, *args, **options):
        seenteam=[]
        todel = True
        for asess in list(Session.objects.all()):
            if not asess.end:
                if asess.start:
                    seenteam.append(asess.driver.team)
                    todel = False
                elif asess.register:
                    seenteam.append(asess.driver.team)
                    todel = False
            if todel:
                asess.delete()
            else:
                asess.start=None
                asess.save()
