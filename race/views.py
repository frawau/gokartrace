# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""
import datetime as dt
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.db.models import Q
from django.views.decorators.csrf import csrf_exempt
from .models import (
    Championship,
    Team,
    Person,
    Round,
    championship_team,
    round_team,
    ChangeLane,
)
from .serializers import ChangeLaneSerializer

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
    cround = Round.objects.filter(
        Q(start__date__range=[start_date, end_date]) & Q(ended__isnull=True)
    ).first()
    return render(
        request, "pages/index.html", {"round": cround, "buttons": button_matrix}
    )


def team_carousel(request):
    end_date = dt.date.today()
    start_date = end_date - dt.timedelta(days=1)
    cround = Round.objects.filter(
        Q(start__date__range=[start_date, end_date]) & Q(ended__isnull=True)
    ).first()

    return render(request, "pages/teamcarousel.html", {"round": cround})


def get_team_card(request):
    team_id = request.GET.get("team_id")
    round_team_instance = get_object_or_404(round_team, pk=team_id)
    cround = round_team_instance.round
    is_paused = cround.round_pause_set.filter(end__isnull=True).exists()
    if cround.started:
        elapsed = cround.time_elapsed.total_seconds()
        remaining = int(max(0, cround.duration.total_seconds() - elapsed))
    else:
        remaining = int(cround.duration.total_seconds())
        is_paused = True

    context = {
        "round_team": round_team_instance,
        "round": cround,
        "is_paused": is_paused,
        "remaining_seconds": remaining,
    }
    html = render(request, "layout/teamcard.html", context).content.decode("utf-8")
    return JsonResponse({"html": html})


def changelane_info(request, lane_number):
    end_date = dt.date.today()
    start_date = end_date - dt.timedelta(days=1)
    cround = Round.objects.filter(
        Q(start__date__range=[start_date, end_date]) & Q(ended__isnull=True)
    ).first()
    change_lane = get_object_or_404(ChangeLane, round=cround, lane=lane_number)
    return render(request, "layout/changelane_info.html", {"change_lane": change_lane})


def changelane_detail(request, lane_number):
    end_date = dt.date.today()
    start_date = end_date - dt.timedelta(days=1)
    cround = Round.objects.filter(
        Q(start__date__range=[start_date, end_date]) & Q(ended__isnull=True)
    ).first()
    change_lane = get_object_or_404(ChangeLane, round=cround, lane=lane_number)
    return render(
        request, "layout/changelane_small_detail.html", {"change_lane": change_lane}
    )


def update_change_lane(request, lane_number):
    end_date = dt.date.today()
    start_date = end_date - dt.timedelta(days=1)
    cround = Round.objects.filter(
        Q(start__date__range=[start_date, end_date]) & Q(ended__isnull=True)
    ).first()
    change_lane = get_object_or_404(ChangeLane, round=cround, lane=lane_number)
    if change_lane.open == True:
        change_lane.next_driver()  # This is the function that updates the driver.
    change_lane.save()
    return render(request, "layout/changelane_info.html", {"change_lane": change_lane})


def changedriver_info(request):
    end_date = dt.date.today()
    start_date = end_date - dt.timedelta(days=1)
    try:
        cround = Round.objects.filter(
            Q(start__date__range=[start_date, end_date]) & Q(ended__isnull=True)
        ).first()
        change_lanes = ChangeLane.objects.filter(round=cround, open=True).order_by(
            "lane"
        )
        return render(
            request, "layout/changedriver_info.html", {"change_lanes": change_lanes}
        )
    except:
        return render(request, "pages/norace.html")


def is_race_director(user):
    return user.is_authenticated and user.groups.filter(name="Race Director").exists()


@login_required
@user_passes_test(is_race_director)
def racecontrol(request):
    end_date = dt.date.today()
    start_date = end_date - dt.timedelta(days=1)
    try:
        cround = Round.objects.filter(
            Q(start__date__range=[start_date, end_date]) & Q(ended__isnull=True)
        ).first()
        lanes = cround.changelane_set.all().order_by("lane")
        return render(
            request, "pages/racecontrol.html", {"round": cround, "lanes": lanes}
        )
    except:
        return render(request, "pages/norace.html")


@login_required
@user_passes_test(is_race_director)
def preracecheck(request):
    end_date = dt.date.today()
    start_date = end_date - dt.timedelta(days=1)
    cround = Round.objects.filter(
        Q(start__date__range=[start_date, end_date]) & Q(ended__isnull=True)
    ).first()
    res = cround.pre_race_check()
    if res:
        return JsonResponse({"result": False, "error": res})

    return JsonResponse({"result": True})


@login_required
@user_passes_test(is_race_director)
def race_start(request):
    # Your start race logic
    return HttpResponse("OK")


@login_required
@user_passes_test(is_race_director)
def falsestart(request):
    # Your false start logic
    return HttpResponse("OK")


@login_required
@user_passes_test(is_race_director)
def racepaused(request):
    # Your pause logic
    return HttpResponse("OK")


@login_required
@user_passes_test(is_race_director)
def racerestart(request):
    # Your restart logic
    return HttpResponse("OK")


@login_required
@user_passes_test(is_race_director)
def falserestart(request):
    # Your false restart logic
    return HttpResponse("OK")


@login_required
@user_passes_test(is_race_director)
def endofrace(request):
    return HttpResponse("OK")


@api_view(["POST"])
def agent_login(request):
    """
    API endpoint for user login and token generation.
    """
    end_date = dt.date.today()
    start_date = end_date - dt.timedelta(days=1)
    cround = Round.objects.filter(
        Q(start__date__range=[start_date, end_date]) & Q(ended__isnull=True)
    ).first()
    if cround is None:
        return Response(
            {"status":"error", "message": "No Championship Round today."}, status=status.HTTP_401_UNAUTHORIZED
        )
    schema = request.scheme
    server = request.META.get('HTTP_HOST') or request.META.get('SERVER_NAME')
    port = request.META.get('SERVER_PORT')

    if ':' in server:
        # If HTTP_HOST already contains the port (e.g., 'example.com:8000')
        server_name, _ = server.split(':', 1)
    else:
        server_name = server

    if port and port not in ('80', '443'):  # Only include non-standard ports
        servurl = f"{schema}://{server_name}:{port}"
    else:
        servurl = f"{schema}://{server_name}"
    username = request.data.get("username")
    password = request.data.get("password")
    user = authenticate(request, username=username, password=password)
    if user is not None:
        if user.groups.filter(name="Queue Scanner").exists():
            token, created = Token.objects.get_or_create(user=user)
            return Response(
                {"status":"ok","token": token.key, "url": servurl+"/driver_queue/"}, status=status.HTTP_200_OK
            )
        elif user.groups.filter(name="Driver Scanner").exists():
            token, created = Token.objects.get_or_create(user=user)
            return Response(
                {"status":"ok","token": token.key, "url": servurl+"driver_change/"}, status=status.HTTP_200_OK
            )
        else:
            return Response(
                {"status":"error", "message": "This is not your role!"}, status=status.HTTP_401_UNAUTHORIZED
            )
    else:
        return Response(
            {"status":"error", "mwssage": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def add_driver_to_queue(request):
    """
    API endpoint that requires authentication using a token.
    """
    try:
        data = json.loads(request.body)  # or request.data if using DRF parsers
        # Process the data and perform the desired actions
        result = {
            "message": "Data received and processed successfully",
            "received_data": data,
        }
        return Response(result, status=status.HTTP_200_OK)

    except json.JSONDecodeError:
        return Response(
            {"error": "Invalid JSON data"}, status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_kart_driver(request):
    """
    API endpoint that requires authentication using a token.
    """
    try:
        data = json.loads(request.body)  # or request.data if using DRF parsers
        # Process the data and perform the desired actions
        result = {
            "message": "Data received and processed successfully",
            "received_data": data,
        }
        return Response(result, status=status.HTTP_200_OK)

    except json.JSONDecodeError:
        return Response(
            {"error": "Invalid JSON data"}, status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
