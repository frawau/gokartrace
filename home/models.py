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
    return f"person/mug_{instance.surname}_{instance.country}_{round(dt.datetime.now().timestamp())}"


def logo_path(instance, filename):
    # file will be uploaded to MEDIA_ROOT/user_<id>/<filename>
    return f"logos/{instance.name}_{round(dt.datetime.now().timestamp())}"


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

    def __str__(self):
        return f"{self.nickname} ({self.firstname} {self.surname})"

    class Meta:
        verbose_name = _("Person")
        verbose_name_plural = _("People")


class Team(models.Model):
    name = models.CharField(max_length=128, unique=True)
    logo = models.ImageField(upload_to=logo_path, null=True, default=None)

    class Meta:
        verbose_name = _("Team")
        verbose_name_plural = _("Teams")


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


class Round(models.Model):
    name = models.CharField(max_length=32)
    championship = models.ForeignKey(Championship, on_delete=models.CASCADE)
    start = models.DateTimeField()
    duration = models.DurationField()
    started = models.DateTimeField(null=True, blank=True)
    ended = models.DateTimeField(null=True, blank=True)
    paused = models.BooleanField(default=False)

    class Meta:
        unique_together = ("championship", "name")

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

    class Meta:
        verbose_name = _("Round")
        verbose_name_plural = _("Rounds")


class round_pause(models.Model):
    round = models.ForeignKey(Round, on_delete=models.CASCADE)
    start = models.DateTimeField(default=dt.datetime.now)
    end = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("Pause")
        verbose_name_plural = _("Pauses")


class championship_team(models.Model):
    championship = models.ForeignKey(Championship, on_delete=models.CASCADE)
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    number = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(99)]
    )

    class Meta:
        unique_together = ("championship", "number")

    class Meta:
        verbose_name = _("Championship Team")
        verbose_name_plural = _("Championship Teams")


class round_team(models.Model):
    round = models.ForeignKey(Round, on_delete=models.CASCADE)
    team = models.ForeignKey(championship_team, on_delete=models.CASCADE)

    class Meta:
        verbose_name = _("Participating Team")
        verbose_name_plural = _("Participating Teams")


class team_member(models.Model):
    team = models.ForeignKey(round_team, on_delete=models.CASCADE)
    member = models.ForeignKey(Person, on_delete=models.CASCADE)
    driver = models.BooleanField(default=True)
    manager = models.BooleanField(default=False)
    weight = models.FloatField()

    class Meta:
        unique_together = ("team", "member")

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
        verbose_name = _("Team Member")
        verbose_name_plural = _("Team Members")


class Session(models.Model):
    round = models.ForeignKey(Round, on_delete=models.CASCADE)
    driver = models.ForeignKey(team_member, on_delete=models.CASCADE)
    register = models.DateTimeField(default=dt.datetime.now)
    start = models.DateTimeField(null=True, blank=True)
    end = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("Session")
        verbose_name_plural = _("Sessions")
