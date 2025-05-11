from django.db import models
from django.db.models import Q, UniqueConstraint
from django_countries.fields import CountryField
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import (
    ValidationError,
    ObjectDoesNotExist,
    MultipleObjectsReturned,
)
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from cryptography.fernet import Fernet
from asgiref.sync import sync_to_async

import datetime as dt
import logging

_log = logging.getLogger(__name__)
# Create your models here.


class UserProfile(models.Model):

    user = models.OneToOneField(User, on_delete=models.CASCADE)

    # __PROFILE_FIELDS__

    # __PROFILE_FIELDS__END

    def __str__(self):
        return self.user.username

    class Meta:
        verbose_name = _("User Profile")
        verbose_name_plural = _("User Profiles")


class Config(models.Model):
    name = models.CharField(max_length=128, unique=True)
    value = models.CharField(max_length=128)

    class Meta:
        verbose_name = _("Configuration")

    def __str__(self):
        return f"Config {self.name} is {self.value}"


def mugshot_path(instance, filename):
    # file will be uploaded to MEDIA_ROOT/user_<id>/<filename>
    return f"static/person/mug_{instance.surname}_{instance.country}_{round(dt.datetime.now().timestamp())}"


def logo_path(instance, filename):
    # file will be uploaded to MEDIA_ROOT/user_<id>/<filename>
    return f"static/logos/{instance.name}_{round(dt.datetime.now().timestamp())}"


class Person(models.Model):
    GENDER = (
        ("M", "♂"),
        ("F", "♀"),
    )
    surname = models.CharField(max_length=32)
    firstname = models.CharField(max_length=32)
    nickname = models.CharField(max_length=32)
    gender = models.CharField(max_length=1, choices=GENDER)
    birthdate = models.DateField()
    country = CountryField()
    mugshot = models.ImageField(upload_to=mugshot_path)
    email = models.EmailField(null=True, default=None)

    class Meta:
        verbose_name = _("Person")
        verbose_name_plural = _("People")

    def __str__(self):
        return f"{self.nickname} ({self.firstname} {self.surname})"


class Team(models.Model):
    name = models.CharField(max_length=128, unique=True)
    logo = models.ImageField(upload_to=logo_path, null=True, default=None)

    class Meta:
        verbose_name = _("Team")
        verbose_name_plural = _("Teams")

    def __str__(self):
        return f"Team {self.name}"


class Championship(models.Model):
    name = models.CharField(max_length=128, unique=True)
    start = models.DateField()
    end = models.DateField()

    @property
    def ongoing(self):
        now = dt.date.today()
        return self.start <= now <= self.end

    class Meta:
        verbose_name = _("Championship")
        verbose_name_plural = _("Championships")

    def __str__(self):
        return f"{self.name}"


class Round(models.Model):
    LIMIT = (
        ("none", "No Time Limit"),
        ("race", "Race Time Limit "),
        ("session", "Session Time Limit"),
    )
    LMETHOD = (
        ("none", "--"),
        ("time", "Time in minutes"),
        ("percent", "Average + N percents"),
    )
    name = models.CharField(max_length=32)
    championship = models.ForeignKey(Championship, on_delete=models.CASCADE)
    start = models.DateTimeField()
    duration = models.DurationField()
    change_lanes = models.IntegerField(
        default=2, validators=[MinValueValidator(1), MaxValueValidator(4)]
    )
    pitlane_open_after = models.DurationField(default=dt.timedelta(minutes=10))
    pitlane_close_before = models.DurationField(default=dt.timedelta(minutes=10))
    limit_time = models.CharField(
        max_length=16,
        choices=LIMIT,
        default="race",
        verbose_name="Maximun Driving Time",
    )
    limit_method = models.CharField(
        max_length=16,
        choices=LMETHOD,
        default="percent",
        verbose_name="Maximun Driving Time Method",
    )
    limit_value = models.IntegerField(
        default=30, verbose_name="Maximun Driving Time Value"
    )
    required_changes = models.IntegerField(
        default=9, verbose_name="Required Driver Changes"
    )
    limit_time_min = models.DurationField(
        default=dt.timedelta(minutes=1),
        verbose_name="Minimum Driving Time",
    )
    weight_penalty = models.JSONField(
        default=list,
        null=True,
        help_text="Weight penalty configuration in format: ['oper', [limit1, value1], [limit2, value2], ...]",
    )
    # No user serviceable parts below
    ready = models.BooleanField(default=False)
    started = models.DateTimeField(null=True, blank=True)
    ended = models.DateTimeField(null=True, blank=True)
    qr_fernet = models.BinaryField(
        max_length=64, default=Fernet.generate_key(), editable=False
    )

    @property
    def ongoing(self):
        if self.started is None:
            return False
        if not self.ended:
            return True
        return False

    @property
    def time_paused(self):
        pass

    @property
    def is_paused(self):
        if self.started:
            return self.round_pause_set.filter(end__isnull=True).exists()
        return True

    @property
    def time_elapsed(self):
        # Calculate paused time within the session duration
        if not self.started:
            return dt.timedelta()
        now = dt.datetime.now()
        totalpause = dt.timedelta()
        for pause in self.round_pause_set.all():
            if pause.end is None:
                now = pause.start
            else:
                totalpause += pause.end - pause.start
        return now - self.started - totalpause

    @sync_to_async
    def async_time_elapsed(self):
        return self.time_elapsed

    @property
    def pit_lane_open(self):
        elapsed = self.time_elapsed
        if elapsed < self.pitlane_open_after:
            return False
        if elapsed > self.duration - self.pitlane_close_before:
            return False
        return True

    @property
    def teams(self):
        """
        Returns a list of Team objects participating in this Round.
        """
        teams = Team.objects.filter(
            championship_team__round_team__round=self
        ).distinct()
        return list(teams)

    @property
    def current_session_info(self):
        """
        Returns a dictionary of active sessions for each team, with participants.
        """
        sessions = {}
        for team in self.teams:
            try:
                active_session = self.session_set.filter(
                    driver__team__team=team,
                    start__isnull=False,
                    end__isnull=True,
                ).latest("start")
                sessions[team.pk] = {
                    "participants": list(active_session.participants.all()),
                    "start_time": active_session.start,
                }
            except self.session_set.model.DoesNotExist:
                sessions[team.pk] = None
        return sessions

    def start_race(self):
        now = dt.datetime.now()
        sessions = self.session_set.filter(
            round=self, register__isnull=False, start__isnull=True, end__isnull=True
        )
        for session in sessions:
            session.start = now
            session.save()
        self.started = now
        self.save()

    def end_race(self):
        now = dt.datetime.now()
        print(f"Ending race at {now}.")
        sessions = self.session_set.filter(
            register__isnull=False, start__isnull=False, end__isnull=True
        )
        for session in sessions:
            session.end = now
            session.save()
        self.ended = now
        self.save()

        sessions = self.session_set.filter(
            round=self, register__isnull=False, start__isnull=True, end__isnull=True
        )
        for session in sessions:
            session.delete()
        ChangeLane.object.all().delete()
        return self.post_race_check()

    def pause_race(self):
        now = dt.datetime.now()
        if self.round_pause_set.filter(round=self, end__isnull=True).exists():
            # There is an open round_pause, so don't pause
            return
        pause = round_pause.objects.create(
            start=now,
            round=self,
        )

    def restart_race(self):
        """
        Resets the 'end' attribute of the latest round_pause only if there are no open round_pauses.
        """

        latest_pause = (
            self.round_pause_set.filter(round=self, end__isnull=True)
            .order_by("-start")
            .first()
        )

        if latest_pause:
            latest_pause.end = dt.datetime.now()
            latest_pause.save()

    def false_start(self):
        sessions = self.session_set.filter(
            round=self, register__isnull=False, start__isnull=False, end__isnull=True
        )
        for session in sessions:
            session.start = None
            session.save()
        self.started = None
        self.save()

    def false_restart(self):
        """
        Resets the 'end' attribute of the latest round_pause only if there are no open round_pauses.
        """
        if self.round_pause_set.filter(end__isnull=True).exists():
            # There is an open round_pause, so don't reset
            return

        latest_pause = self.round_pause_set.order_by("-start").first()

        if latest_pause:
            latest_pause.end = None
            latest_pause.save()

    def pre_race_check(self):
        """
        Checks that each team has exactly one driver with a registered but unstarted session,
        and that all drivers have a non-zero weight.
        """
        errors = []

        for round_team_instance in self.round_team_set.all():
            drivers = round_team_instance.team_member_set.filter(driver=True)

            registered_drivers = []
            for driver in drivers:
                sessions = driver.session_set.filter(
                    register__isnull=False,
                    start__isnull=True,
                    end__isnull=True,
                )

                if sessions.exists():
                    registered_drivers.append(driver)

                if driver.weight <= 10:
                    errors.append(
                        f"Driver {driver.member.nickname} in team {round_team_instance.team.team.name} has an unlikely weight."
                    )

            if len(registered_drivers) != 1:
                errors.append(
                    f"Team {round_team_instance.team.team.name} ({round_team_instance.team.number}) has {len(registered_drivers)} registered to start. Expected 1."
                )

        if errors:
            return errors
        else:
            self.ready = True
            self.save()
            for i in range(self.change_lanes):
                lane = ChangeLane.objects.create(
                    driver=None,
                    round=self,
                    lane=i + 1,
                )
            return None

    def post_race_check(self):
        """
        Checks that each team has exactly one driver with a registered but unstarted session,
        and that all drivers have a non-zero weight.
        """
        errors = []
        # TODO Check the driving time, that all drivers did dive,...

    def change_queue(self):
        sessions = self.session_set.filter(
            register__isnull=False, start__isnull=True, end__isnull=True
        ).order_by("register")
        return sessions

    def next_driver_change(self):
        if not self.pit_lane_open:
            return "close"
        # Get drivers currently in a ChangeLane
        drivers_in_lanes = ChangeLane.objects.filter(
            round=self, driver__isnull=False
        ).values_list("driver_id", flat=True)

        # Get the next session excluding those drivers
        session = (
            self.session_set.filter(
                register__isnull=False, start__isnull=True, end__isnull=True
            )
            .exclude(driver_id__in=drivers_in_lanes)
            .order_by("register")
            .first()
        )
        return session

    def driver_register(self, driver):
        """
        Creates a Session for the given driver and sets the registered time to now.
        """
        retval = {
            "message": f"This should not have happened!",
            "status": "error",
        }
        if self.started and not self.pit_lane_open:
            raise ValidationError("The pit lane is closed.")

        if not driver.driver:
            raise ValidationError(f"{driver.member.nickname} is not a driver.")

        now = dt.datetime.now()
        asession = self.session_set.filter(
            driver=driver, register__isnull=False, start__isnull=False, end__isnull=True
        ).first()
        if asession:
            return {
                "message": f"Driver {driver.member.nickname} from team {driver.team.number} is currently driving!",
                "status": "error",
            }
        #
        # Did we already register?
        pending_sessions = self.session_set.filter(
            register__isnull=False, start__isnull=True, end__isnull=True
        ).order_by("register")

        # Get the top self.change_lanes sessions
        top_sessions = pending_sessions[: self.change_lanes]

        session = self.session_set.filter(
            driver=driver, register__isnull=False, start__isnull=True, end__isnull=True
        ).first()
        if session:
            if self.started and session in top_sessions:
                return {
                    "message": f"Driver {driver.member.nickname} from team {driver.team.number} is due in pit lane. Cannot be removed.",
                    "status": "error",
                }
            else:
                session.delete()
                return {
                    "message": f"Driver {driver.member.nickname} from team {driver.team.number} was removed.",
                    "status": "warning",
                }
        else:
            session = Session.objects.create(
                driver=driver,
                round=self,
                register=now,
            )
            retval = {
                "message": f"Driver {driver.member.nickname} from team {driver.team.number} registered.",
                "status": "ok",
            }
        if self.started:
            alane = (
                ChangeLane.objects.filter(round=self, driver__isnull=True)
                .order_by("lane")
                .first()
            )
            if alane:
                alane.driver = driver
                alane.save()
        return retval

    def driver_endsession(self, driver):
        """
        Ends the given driver's session and starts the next driver's session on the same team.
        """

        retval = {
            "message": f"This should not have happened!",
            "status": "error",
        }
        now = dt.datetime.now()

        # 1. End the current driver's session
        try:
            current_session = driver.session_set.get(
                round=self,
                register__isnull=False,
                start__isnull=False,
                end__isnull=True,
            )
        except ObjectDoesNotExist:
            raise ValidationError(f"Driver {driver} has no current session.")
        except MultipleObjectsReturned:
            raise ValidationError(f"Driver {driver} has multiple current sessions.")

        # 2. Find and start the next driver's session
        try:
            related_team_members = team_member.objects.filter(team=driver.team)

            # Find the oldest active session among these team members
            next_session = (
                Session.objects.filter(
                    driver__in=related_team_members,
                    start__isnull=True,
                    end__isnull=True,
                )
                .order_by("register")
                .first()
            )

            if next_session:
                current_session.end = now
                current_session.save()
                next_session.start = now
                next_session.save()

                retval = {
                    "message": f"Driver {driver.member.nickname} from team {driver.team.number} ended session.",
                    "status": "ok",
                }
                # Update change lane
                alane = ChangeLane.objects.filter(
                    round=self, driver=next_session.driver
                ).first()
                if alane:
                    alane.next_driver()
                else:
                    print(f"Error: Could not find lane for {next_session.driver}")
            else:
                retval = {
                    "message": f"Keeo driving no one is waiting for teasm {driver.team.number}.",
                    "status": "error",
                }

        except ObjectDoesNotExist:
            # Driver is not associated with a round_team
            print(f"Driver {driver} is not associated with a round_team.")
            retval["message"] = f"Driver {driver} is not associated with a round_team."
        except MultipleObjectsReturned:
            # Driver is associated with multiple round_teams (unexpected)
            print(f"Driver {driver} is associated with multiple round_teams.")
            retval[
                "message"
            ] = f"Driver {driver} is associated with multiple round_teams."
        return retval

    def driver_time_limit(self, rteam):
        """
        For a team member, calculate the max time driving
        """
        if self.limit_time == "none":
            return None, None
        if self.limit_method == "none":
            return None, None
        if self.limit_method == "time":
            return self.limit_time, self.limit_value
        elif self.limit_method == "percent":
            driver_count = team_member.objects.filter(team=rteam, driver=True).count()
            maxt = (self.duration / driver_count) * (1 + self.limit_value / 100)
            return self.limit_time, maxt
        return None, None

    def clean(self):
        super().clean()  # Call the parent class's clean method

        if self.weight_penalty:
            operatorok = False
            for arule in self.weight_penalty:
                if (
                    isinstance(arule, list)
                    and len(arule) == 2
                    and isinstance(arule[0], (int, float))
                    and isinstance(arule[1], (int, float))
                ):
                    continue
                if (
                    isinstance(arule, str)
                    and arule in [">=", "<=", ">", "<"]
                    and not operatorok
                ):
                    operatorok = True
                    continue
                raise ValidationError(
                    "Only one operator is allowed for weight penalty. All others must be numeric lists of the form [<weight limit>, <penalty>]"
                )
            if not operatorok:
                raise ValidationError(
                    "Weight penaly must have an operator in >=, <=, > or <"
                )

    def save(self, *args, **kwargs):
        if self.weight_penalty:
            rules = self.weight_penalty
            operator = None
            newrules = []
            for arule in rules:
                if isinstance(arule, list):
                    newrules.append(arule)
                else:
                    operator = arule.encode("ascii").decode()

            if operator in [">=", ">"]:
                newrules.sort(key=lambda item: item[0], reverse=True)
            else:
                newrules.sort(key=lambda item: item[0])

            # Reconstruct the list with the operator and sorted pairs
            self.weight_penalty = [operator] + newrules
        else:
            self.weight_penalty = None

        super().save(*args, **kwargs)

    class Meta:
        unique_together = ("championship", "name")
        verbose_name = _("Round")
        verbose_name_plural = _("Rounds")

    def __str__(self):
        return f"{self.name} of {self.championship.name}"


class round_pause(models.Model):
    round = models.ForeignKey(Round, on_delete=models.CASCADE)
    start = models.DateTimeField(default=dt.datetime.now)
    end = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("Pause")
        verbose_name_plural = _("Pauses")

    def __str__(self):
        return f"{self.round.name} pause"


class championship_team(models.Model):
    championship = models.ForeignKey(Championship, on_delete=models.CASCADE)
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    number = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(99)]
    )

    class Meta:
        unique_together = (("championship", "number"), ("championship", "team"))
        verbose_name = _("Championship Team")
        verbose_name_plural = _("Championship Teams")

    def __str__(self):
        return f"({self.number}) {self.team.name} in {self.championship.name}."


class round_team(models.Model):
    round = models.ForeignKey(Round, on_delete=models.CASCADE)
    team = models.ForeignKey(championship_team, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("round", "team")
        verbose_name = _("Participating Team")
        verbose_name_plural = _("Participating Teams")
        ordering = ["team__number"]

    @property
    def name(self):
        return self.team.team.name

    @property
    def number(self):
        return self.team.number

    def __str__(self):
        return f"{self.team} in {self.round}"


class team_member(models.Model):
    team = models.ForeignKey(round_team, on_delete=models.CASCADE)
    member = models.ForeignKey(Person, on_delete=models.CASCADE)
    driver = models.BooleanField(default=True)
    manager = models.BooleanField(default=False)
    weight = models.FloatField(default=0)

    def clean(self):
        super().clean()
        if self.manager:
            count = (
                team_member.objects.filter(team=self.team, manager=True)
                .exclude(pk=self.pk)
                .count()
            )
            if count > 0:
                raise ValidationError("Only one manager allowed per round and team.")
        # Custom validation for unique member per round
        existing_member_teams = team_member.objects.filter(
            member=self.member, team__round=self.team.round
        ).exclude(
            pk=self.pk
        )  # exclude the current object.

        if existing_member_teams.exists():
            raise ValidationError(
                "A person can only be a member of one team per round."
            )

    @property
    def time_spent(self):
        sessions = self.session_set.filter(driver=self, start__isnull=False)
        total_time = dt.timedelta(0)
        now = dt.datetime.now()
        for session in sessions:
            if session.end:
                session_time = session.end - session.start
            else:
                session_time = now - session.start
            paused_time = dt.timedelta(0)

            # Calculate paused time within the session duration
            if session.end:
                pauses = self.team.round.round_pause_set.filter(
                    start__lte=session.end,
                    end__gte=session.start,
                )
            else:
                pauses = self.team.round.round_pause_set.filter(
                    Q(start__lte=now), Q(end__gte=session.start) | Q(end__isnull=True)
                )

            for pause in pauses:
                pause_start = max(pause.start, session.start)
                pause_end = min(
                    pause.end or now, session.end or now
                )  # if pause.end is null, use now.
                paused_time += pause_end - pause_start

            total_time += session_time - paused_time
        return total_time

    @property
    def current_session(self):
        total_time = dt.timedelta(0)
        try:
            sessions = self.session_set.filter(
                driver=self, start__isnull=False, end__isnull=True
            )
            now = dt.datetime.now()
            for session in sessions:
                session_time = now - session.start
                paused_time = dt.timedelta(0)

                # Calculate paused time within the session duration

                pauses = self.team.round.round_pause_set.filter(
                    Q(start__lte=now), Q(end__gte=session.start) | Q(end__isnull=True)
                )

                for pause in pauses:
                    pause_start = max(pause.start, session.start)
                    pause_end = pause.end or now  # if pause.end is null, use now.
                    paused_time += pause_end - pause_start

                total_time += session_time - paused_time
                return total_time
        except ObjectDoesNotExist:
            # Handle the case where no session is found
            pass
        except MultipleObjectsReturned:
            _log.critical("There should be only one active session per team/driver")
        except Exception as e:
            _log.critical(f"Active session exception: {e}")
        finally:
            return total_time

    @property
    def ontrack(self):
        return self.session_set.filter(
            driver=self, start__isnull=False, end__isnull=True
        ).exists()

    @property
    def isready(self):
        return self.session_set.filter(driver=self, end__isnull=True).exists()

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    class Meta:
        unique_together = ("team", "member")
        verbose_name = _("Team Member")
        verbose_name_plural = _("Team Members")

    def __str__(self):
        return f"{self.member.nickname} for {self.team.team} in {self.team.round}"

    @property
    def weight_penalty(self):
        rules = self.team.round.weight_penalty
        if not rules:
            return None
        oper = rules[0]
        rules = rules[1:]
        if oper == ">":
            checkme = lambda x, y: x > y
        elif oper == ">=":
            checkme = lambda x, y: x >= y
        elif oper == "<":
            checkme = lambda x, y: x < y
        else:
            checkme = lambda x, y: x <= y

        for l, v in rules:
            if checkme(self.weight, l):
                return v


class Session(models.Model):
    cround = models.ForeignKey(Round, on_delete=models.CASCADE)
    driver = models.ForeignKey(team_member, on_delete=models.CASCADE)
    register = models.DateTimeField(default=dt.datetime.now)
    start = models.DateTimeField(null=True, blank=True)
    end = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("Session")
        verbose_name_plural = _("Sessions")

    def __str__(self):
        return f"{self.driver.member.nickname} in {self.cround}"


class ChangeLane(models.Model):
    round = models.ForeignKey(Round, on_delete=models.CASCADE)
    lane = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(4)])
    driver = models.ForeignKey(
        team_member, null=True, blank=True, on_delete=models.SET_NULL
    )
    open = models.BooleanField(default=False)

    def next_driver(self):
        sess = self.round.next_driver_change()
        print(f"Next driver from {sess}")
        if sess == "close":
            self.open = False
            self.driver = None
        elif sess:
            self.driver = sess.driver
        else:
            self.driver = None
        self.save()

    class Meta:
        unique_together = ("round", "lane")
        constraints = [
            UniqueConstraint(
                fields=["driver"],
                condition=Q(driver__isnull=False),
                name="unique_driver_when_not_null",
            )
        ]

    def __str__(self):
        return f"{self.cround.name} Lane {self.lane}"
