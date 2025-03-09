# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""
import datetime as dt
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from rest_framework import generics
from rest_framework.response import Response
from django.db.models import Q
from .models import Championship, Team, Person, Round, championship_team, round_team, ChangeLane
from .serializers import ChangeLaneSerializer
from rest_framework.decorators import api_view
# Create your views here.


def index(request):
    # Page from the theme
    button_matrix = [
        [
            {"label": "Team Carousel", "url": "/teamcarousel/"},
            {"label": "Driver's Queue", "url": "/driverqueue/"},
            {"label": "Drivers on Track", "url": "/driverontrack/"},
        ],
        [
            {"label": "Monitor One Team", "url": "/oneteam/"},
            {"label": "Monitor One Driver", "url": "/onedriver/"},
            {"label": "ekskip", "url": ""},
        ],
    ]
    end_date = dt.date.today()
    start_date = end_date - dt.timedelta(days=1)
    round = Round.objects.filter(
        Q(start__date__range=[start_date, end_date]) & Q(ended__isnull=True)
    ).first()
    return render(
        request, "pages/index.html", {"round": round, "buttons": button_matrix}
    )


def team_carousel(request):
    end_date = dt.date.today()
    start_date = end_date - dt.timedelta(days=1)
    round = Round.objects.filter(
        Q(start__date__range=[start_date, end_date]) & Q(ended__isnull=True)
    ).first()

    return render(request, "pages/teamcarousel.html", {"round": round})


def get_team_card(request):
    team_id = request.GET.get("team_id")
    round_team_instance = get_object_or_404(round_team, pk=team_id)
    context = {
        "round_team": round_team_instance,
    }
    html = render(request, "layout/teamcard.html", context).content.decode("utf-8")
    return JsonResponse({"html": html})

class ChangeLaneDetail(generics.RetrieveAPIView):
    queryset = ChangeLane.objects.all()
    serializer_class = ChangeLaneSerializer
    lookup_field = 'lane'

@api_view(['GET'])
def test_changelane(request):
    try:
        changelane = ChangeLane.objects.get(lane=1)  # Replace 1 with a valid lane number
        serializer = ChangeLaneSerializer(changelane)
        return Response(serializer.data)
    except ChangeLane.DoesNotExist:
        return Response({'error': 'ChangeLane not found'}, status=404)
