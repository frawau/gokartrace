from django.db import models
from django_countries.fields import CountryField
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _

import datetime as dt

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


def mugshot_path(instance, filename):
    # file will be uploaded to MEDIA_ROOT/user_<id>/<filename>
    return f"staticfiles/person/mug_{instance.surname}_{instance.country}_{round(dt.datetime.now().timestamp())}"


def logo_path(instance, filename):
    # file will be uploaded to MEDIA_ROOT/user_<id>/<filename>
    return f"staticfiles/logos/{instance.name}_{round(dt.datetime.now().timestamp())}"


class Person(models.Model):
    GENDER = (
        ("M", "🕺"),
        ("F", "💃"),
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
    name = models.CharField(max_length=32)
    championship = models.ForeignKey(Championship, on_delete=models.CASCADE)
    start = models.DateTimeField()
    duration = models.DurationField()
    started = models.DateTimeField(null=True, blank=True)
    ended = models.DateTimeField(null=True, blank=True)
    paused = models.BooleanField(default=False)

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
                    participants__team__team=team,
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
        unique_together = ("championship", "number")
        unique_together = ("championship", "team")
        verbose_name = _("Championship Team")
        verbose_name_plural = _("Championship Teams")

    def __str__(self):
        return f"{self.team.name} in {self.championship.name}."


class round_team(models.Model):
    round = models.ForeignKey(Round, on_delete=models.CASCADE)
    team = models.ForeignKey(championship_team, on_delete=models.CASCADE)

    @property
    def members_time_spent(self):
        """
        Returns a dictionary of members and their total time spent in sessions for this round,
        excluding paused time.
        """
        time_spent = {}
        for member in self.team_member_set.all():
            sessions = member.session_set.filter(
                round=self.round, start__isnull=False, end__isnull=False
            )
            total_time = dt.timedelta(0)  # Initialize total time

            for session in sessions:
                session_time = session.end - session.start
                paused_time = dt.timedelta(0)

                # Calculate paused time within the session duration
                pauses = self.round.round_pause_set.filter(
                    start__lte=session.end,
                    end__gte=session.start,
                )

                for pause in pauses:
                    pause_start = max(pause.start, session.start)
                    pause_end = min(
                        pause.end or datetime.now(timezone.utc), session.end
                    )  # if pause.end is null, use now.
                    paused_time += pause_end - pause_start

                total_time += session_time - paused_time

            time_spent[member.pk] = total_time

        return time_spent

    class Meta:
        unique_together = ("round", "team")
        verbose_name = _("Participating Team")
        verbose_name_plural = _("Participating Teams")

    def __str__(self):
        return f"{self.team} in {self.round}"


class team_member(models.Model):
    team = models.ForeignKey(round_team, on_delete=models.CASCADE)
    member = models.ForeignKey(Person, on_delete=models.CASCADE)
    driver = models.BooleanField(default=True)
    manager = models.BooleanField(default=False)
    weight = models.FloatField()

    def clean(self):
        super().clean()
        if self.manager:
            count = (
                team_member.objects.filter(
                    round=self.round, team=self.team, manager=True
                )
                .exclude(pk=self.pk)
                .count()
            )
            if count > 0:
                raise ValidationError("Only one manager allowed per round and team.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    class Meta:
        unique_together = (
            "member",
            "team__round",
        )  # Essentially one person can only be in one team.
        unique_together = ("team", "member")
        verbose_name = _("Team Member")
        verbose_name_plural = _("Team Members")

    def __str__(self):
        return f"{self.member.nickname} for {self.team.team} in {self.team.round}"


class Session(models.Model):
    round = models.ForeignKey(Round, on_delete=models.CASCADE)
    driver = models.ForeignKey(team_member, on_delete=models.CASCADE)
    register = models.DateTimeField(default=dt.datetime.now)
    start = models.DateTimeField(null=True, blank=True)
    end = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("Session")
        verbose_name_plural = _("Sessions")

    def __str__(self):
        return f"{self.driver.nickname} in {self.round}"
