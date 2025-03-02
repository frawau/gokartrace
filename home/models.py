# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _

# Create your models here.

class UserProfile(models.Model):

    user = models.OneToOneField(User, on_delete=models.CASCADE)

    #__PROFILE_FIELDS__

    #__PROFILE_FIELDS__END

    def __str__(self):
        return self.user.username
    
    class Meta:
        verbose_name        = _("UserProfile")
        verbose_name_plural = _("UserProfile")

#__MODELS__
class Championship(models.Model):

    #__Championship_FIELDS__
    name = models.CharField(max_length=255, null=True, blank=True)
    start = models.DateTimeField(blank=True, null=True, default=timezone.now)
    end = models.DateTimeField(blank=True, null=True, default=timezone.now)

    #__Championship_FIELDS__END

    class Meta:
        verbose_name        = _("Championship")
        verbose_name_plural = _("Championship")


class Person(models.Model):

    #__Person_FIELDS__
    firstname = models.CharField(max_length=255, null=True, blank=True)
    nickname = models.CharField(max_length=255, null=True, blank=True)
    birthdate = models.DateTimeField(blank=True, null=True, default=timezone.now)
    gender = models.CharField(max_length=255, null=True, blank=True)
    country = models.CharField(max_length=255, null=True, blank=True)
    email = models.CharField(max_length=255, null=True, blank=True)
    mugshot = models.CharField(max_length=255, null=True, blank=True)

    #__Person_FIELDS__END

    class Meta:
        verbose_name        = _("Person")
        verbose_name_plural = _("Person")


class Team(models.Model):

    #__Team_FIELDS__
    name = models.CharField(max_length=255, null=True, blank=True)
    logo = models.CharField(max_length=255, null=True, blank=True)

    #__Team_FIELDS__END

    class Meta:
        verbose_name        = _("Team")
        verbose_name_plural = _("Team")


class Round(models.Model):

    #__Round_FIELDS__
    championship = models.ForeignKey(Championship, on_delete=models.CASCADE)
    start = models.DateTimeField(blank=True, null=True, default=timezone.now)
    duration = models.IntegerField(null=True, blank=True)
    started = models.DateTimeField(blank=True, null=True, default=timezone.now)
    ended = models.DateTimeField(blank=True, null=True, default=timezone.now)
    paused = models.BooleanField()

    #__Round_FIELDS__END

    class Meta:
        verbose_name        = _("Round")
        verbose_name_plural = _("Round")


class Round_Pause(models.Model):

    #__Round_Pause_FIELDS__
    round = models.ForeignKey(Round, on_delete=models.CASCADE)
    start = models.DateTimeField(blank=True, null=True, default=timezone.now)
    end = models.DateTimeField(blank=True, null=True, default=timezone.now)

    #__Round_Pause_FIELDS__END

    class Meta:
        verbose_name        = _("Round_Pause")
        verbose_name_plural = _("Round_Pause")


class Championship_Team(models.Model):

    #__Championship_Team_FIELDS__
    championship = models.ForeignKey(Championship, on_delete=models.CASCADE)
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    number = models.IntegerField(null=True, blank=True)

    #__Championship_Team_FIELDS__END

    class Meta:
        verbose_name        = _("Championship_Team")
        verbose_name_plural = _("Championship_Team")


class Round_Team(models.Model):

    #__Round_Team_FIELDS__
    round = models.ForeignKey(Round, on_delete=models.CASCADE)
    team = models.ForeignKey(Team, on_delete=models.CASCADE)

    #__Round_Team_FIELDS__END

    class Meta:
        verbose_name        = _("Round_Team")
        verbose_name_plural = _("Round_Team")


class Team_Member(models.Model):

    #__Team_Member_FIELDS__
    team = models.ForeignKey(round_team, on_delete=models.CASCADE)
    member = models.ForeignKey(Person, on_delete=models.CASCADE)
    driver = models.BooleanField()
    manager = models.BooleanField()
    weight = models.IntegerField(null=True, blank=True)

    #__Team_Member_FIELDS__END

    class Meta:
        verbose_name        = _("Team_Member")
        verbose_name_plural = _("Team_Member")


class Session(models.Model):

    #__Session_FIELDS__
    round = models.ForeignKey(Round, on_delete=models.CASCADE)
    driver = models.ForeignKey(team_member, on_delete=models.CASCADE)
    register = models.DateTimeField(blank=True, null=True, default=timezone.now)
    start = models.DateTimeField(blank=True, null=True, default=timezone.now)
    end = models.DateTimeField(blank=True, null=True, default=timezone.now)

    #__Session_FIELDS__END

    class Meta:
        verbose_name        = _("Session")
        verbose_name_plural = _("Session")



#__MODELS__END
