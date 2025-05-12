# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

from django.urls import path
from . import consumers
from . import views
from .pdfcardview import GenerateCardPDF
from .teammgt import TeamMembersView

urlpatterns = [
    path("", views.index, name="Home"),
    path("teamcarousel/", views.team_carousel, name="Participating Teams"),
    path("racecontrol/", views.racecontrol, name="Race Control"),
    path("get_team_card/", views.get_team_card, name="Team Card"),
    # path('ws/pitlane/<int:lane_number>/', views.changelane_info, name = 'change_lane_ws'),
    path("pitlane/<int:lane_number>/", views.changelane_info, name="Change Lane"),
    path(
        "pitlanedetail/<int:lane_number>/",
        views.changelane_detail,
        name="Change Lane Info",
    ),
    path("changedriver/", views.changedriver_info, name="Call for Driver Change"),
    path("preracecheck/", views.preracecheck, name="preracecheck"),
    path("race/start/", views.race_start, name="race_start"),
    path("falsestart/", views.falsestart, name="falsestart"),
    path("racepaused/", views.racepaused, name="racepaused"),
    path("racerestart/", views.racerestart, name="racerestart"),
    path("falserestart/", views.falserestart, name="falserestart"),
    path("endofrace/", views.endofrace, name="endofrace"),
    path("generate_card/", GenerateCardPDF.as_view(), name="generate_cards"),
    path("agent_login/", views.agent_login, name="Agent Login"),
    path("driver_queue/", views.add_driver_to_queue, name="Driver Queue"),
    path("driver_change/", views.change_kart_driver, name="Driver Change"),
    path("pending_drivers/", views.pending_drivers, name="pending_drivers"),
    path(
        "api/driver/<int:driver_id>/info/",
        views.driver_info_api,
        name="driver_info_api",
    ),
    path("round_info/", views.round_stats_view, name="round_info"),
    # Admin stuffs
    path("rounds/update/", views.round_list_update, name="rounds_list"),
    path("rounds/form/", views.round_form, name="round_form"),
    path("rounds/update/<int:round_id>/", views.update_round, name="update_round"),
    path("rounds/team/", TeamMembersView.as_view(), name="team_members"),
    path("driver/add/", views.create_driver, name="add_driver"),
    path("team/add/", views.create_team, name="add_team"),
    path("get_round_status/", views.get_round_status, name="get_round_status"),
    path("get_race_lanes/", views.get_race_lanes, name="get_race_lane"),
    path("singleteam/", views.singleteam_view, name="single_team"),
    path("join_championship/", views.join_championship_view, name="join_championship"),
    path("api/get_teams/", views.get_available_teams, name="get_available_teams"),
    path("api/get_numbers/", views.get_available_numbers, name="get_available_numbers"),
]
