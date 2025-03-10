# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

from django.urls import path
from . import consumers
from . import views

urlpatterns = [
    path("", views.index, name="Everybody"),
    path("teamcarousel/", views.team_carousel, name="Participating Teams"),
    path("get_team_card/", views.get_team_card, name="Team Card"),
    path('changelanes/<int:lane>/', views.changelane_ifo.as_view()),
    path("testlane/", views.test_changelane, name="Pit Lane"),
    path('ws/changelane/<int:lane_number>/', views.changelane_info, name = 'change_lane_ws')
]
