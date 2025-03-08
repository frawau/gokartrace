# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="Everybody"),
    path("teamcarousel", views.team_carousel, name="Participating Teams"),
]
