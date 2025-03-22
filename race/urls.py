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
    path("racecontrol/", views.racecontrol, name="Race Control"),
    path("get_team_card/", views.get_team_card, name="Team Card"),
    # path('ws/pitlane/<int:lane_number>/', views.changelane_info, name = 'change_lane_ws'),
    path('pitlane/<int:lane_number>/', views.changelane_info, name='Change Lane'),
    path('changedriver/', views.changedriver_info, name='Call for Driver Change'),
]
