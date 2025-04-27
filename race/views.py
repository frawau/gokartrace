# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""
import datetime as dt
import json
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_http_methods
from django.contrib.auth.models import User
from django.contrib import messages
from django.urls import reverse
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.decorators import (
    api_view,
    permission_classes,
    authentication_classes,
)
from rest_framework.permissions import IsAuthenticated, AllowAny
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
    team_member,
    ChangeLane,
)
from .serializers import ChangeLaneSerializer
from .utils import datadecode
from .forms import DriverForm, TeamForm
from django.template import loader

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
            {"label": "Monitor One Team", "url": "/singleteam/"},
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
        elapsed = round(cround.time_elapsed.total_seconds())
        remaining = int(max(0, round(cround.duration.total_seconds() - elapsed)))
    else:
        remaining = round(cround.duration.total_seconds())
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


def is_admin_user(user):
    return user.is_authenticated and user.groups.filter(name="Admin").exists()


@login_required
@user_passes_test(is_race_director)
def racecontrol(request):
    end_date = dt.date.today()
    start_date = end_date - dt.timedelta(days=1)
    try:
        cround = Round.objects.filter(
            Q(start__date__range=[start_date, end_date]) & Q(ended__isnull=True)
        ).first()
        lanes = cround.change_lanes
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
    end_date = dt.date.today()
    start_date = end_date - dt.timedelta(days=1)
    cround = Round.objects.filter(
        Q(start__date__range=[start_date, end_date]) & Q(ended__isnull=True)
    ).first()
    cround.start_race()
    return JsonResponse({"result": True})


@login_required
@user_passes_test(is_race_director)
def falsestart(request):
    end_date = dt.date.today()
    start_date = end_date - dt.timedelta(days=1)
    cround = Round.objects.filter(
        Q(start__date__range=[start_date, end_date]) & Q(ended__isnull=True)
    ).first()
    cround.false_start()
    return JsonResponse({"result": True})


@login_required
@user_passes_test(is_race_director)
def racepaused(request):
    end_date = dt.date.today()
    start_date = end_date - dt.timedelta(days=1)
    cround = Round.objects.filter(
        Q(start__date__range=[start_date, end_date]) & Q(ended__isnull=True)
    ).first()
    cround.pause_race()
    return JsonResponse({"result": True})


@login_required
@user_passes_test(is_race_director)
def racerestart(request):
    end_date = dt.date.today()
    start_date = end_date - dt.timedelta(days=1)
    cround = Round.objects.filter(
        Q(start__date__range=[start_date, end_date]) & Q(ended__isnull=True)
    ).first()
    cround.restart_race()
    return JsonResponse({"result": True})


@login_required
@user_passes_test(is_race_director)
def falserestart(request):
    # Your false restart logic
    end_date = dt.date.today()
    start_date = end_date - dt.timedelta(days=1)
    cround = Round.objects.filter(
        Q(start__date__range=[start_date, end_date]) & Q(ended__isnull=True)
    ).first()
    cround.false_restart()
    return JsonResponse({"result": True})


@login_required
@user_passes_test(is_race_director)
def endofrace(request):
    errs = self.end_race()
    return JsonResponse({"result": True})


@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
@authentication_classes([])
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
            {"status": "error", "message": "No Championship Round today."},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    schema = request.scheme
    server = request.META.get("HTTP_HOST") or request.META.get("SERVER_NAME")
    port = request.META.get("SERVER_PORT")

    if ":" in server:
        # If HTTP_HOST already contains the port (e.g., 'example.com:8000')
        server_name, _ = server.split(":", 1)
    else:
        server_name = server

    if port and port not in ("80", "443"):  # Only include non-standard ports
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
                {"status": "ok", "token": token.key, "url": servurl + "/driver_queue/"},
                status=status.HTTP_200_OK,
            )
        elif user.groups.filter(name="Driver Scanner").exists():
            token, created = Token.objects.get_or_create(user=user)
            return Response(
                {
                    "status": "ok",
                    "token": token.key,
                    "url": servurl + "/driver_change/",
                },
                status=status.HTTP_200_OK,
            )
        else:
            return Response(
                {"status": "error", "message": "This is not your role!"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
    else:
        return Response(
            {"status": "error", "message": "Invalid credentials"},
            status=status.HTTP_401_UNAUTHORIZED,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def add_driver_to_queue(request):
    """
    API endpoint that requires authentication using a token.
    """
    try:
        end_date = dt.date.today()
        start_date = end_date - dt.timedelta(days=1)
        cround = Round.objects.filter(
            Q(start__date__range=[start_date, end_date]) & Q(ended__isnull=True)
        ).first()
        payload = json.loads(request.body)  # or request.data if using DRF parsers

        tmpk = datadecode(cround, payload["data"])
        tmember = team_member.objects.get(pk=tmpk)
        # Process the data and perform the desired actions
        try:
            result = cround.driver_register(tmember)
        except Exception as e:
            result = {
                "message": f"Error for {tmember}: {e}",
                "status": "error",
            }
        # print(result)
        return Response(result, status=status.HTTP_200_OK)

    except json.JSONDecodeError:
        return Response(
            {"status": "error", "message": "Invalid JSON data"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except Exception as e:
        return Response(
            {"status": "error", "message": f"Exception: {e}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_kart_driver(request):
    """
    API endpoint that requires authentication using a token.
    """
    try:
        end_date = dt.date.today()
        start_date = end_date - dt.timedelta(days=1)
        cround = Round.objects.filter(
            Q(start__date__range=[start_date, end_date]) & Q(ended__isnull=True)
        ).first()
        payload = json.loads(request.body)  # or request.data if using DRF parsers

        tmpk = datadecode(cround, payload["data"])
        tmember = team_member.objects.get(pk=tmpk)
        # Process the data and perform the desired actions
        try:
            result = cround.driver_endsession(tmember)
        except Exception as e:
            result = {
                "message": f"Error for {tmember}: {e}",
                "status": "error",
            }
        # print(result)
        return Response(result, status=status.HTTP_200_OK)

    except json.JSONDecodeError:
        return Response(
            {"status": "error", "message": "Invalid JSON data"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except Exception as e:
        return Response(
            {"status": "error", "message": f"Exception: {e}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@login_required
@user_passes_test(is_admin_user)
def round_list_update(request):
    """View to list all rounds and provide the form to update them"""
    end_date = dt.date.today().replace(month=12).replace(day=31)
    start_date = dt.date.today().replace(month=1).replace(day=1)
    champ = Championship.objects.filter(start=start_date, end=end_date).get()
    rounds = Round.objects.filter(championship=champ).order_by("start")
    context = {"rounds": rounds}

    if request.method == "GET" and "round_id" in request.GET:
        try:
            selected_round = Round.objects.get(pk=request.GET["round_id"])
            context["selected_round"] = selected_round
        except Round.DoesNotExist:
            messages.error(request, "Round not found")

    return render(request, "pages/roundedit.html", context)


@login_required
@user_passes_test(is_admin_user)
@require_http_methods(["GET"])
def round_form(request):
    """HTMX view to return the round form partial"""
    round_id = request.GET.get("round_id")

    if not round_id:
        return HttpResponse("Please select a round")

    try:
        round_obj = Round.objects.get(pk=round_id)

        # Ensure weight_penalty is properly formatted
        if not round_obj.weight_penalty:
            round_obj.weight_penalty = [">=", [0, 0]]

        # If it's a string, try to parse it
        if isinstance(round_obj.weight_penalty, str):
            try:
                round_obj.weight_penalty = json.loads(round_obj.weight_penalty)
            except json.JSONDecodeError:
                round_obj.weight_penalty = [">=", [0, 0]]

        # Convert to JSON string for template
        context = {
            "round": round_obj,
        }
        return render(request, "layout/roundedit.html", context)
    except Round.DoesNotExist:
        return HttpResponse("Round not found")


@login_required
@user_passes_test(is_admin_user)
@require_http_methods(["POST"])
def update_round(request, round_id):
    """Handle the form submission to update a round"""
    round_obj = get_object_or_404(Round, pk=round_id)

    try:
        # Update basic fields
        round_obj.name = request.POST.get("name")
        round_obj.start = request.POST.get("start")

        # Parse duration strings
        def parse_duration(duration_str):
            if ":" in duration_str:
                parts = duration_str.split(":")
                if len(parts) == 3:  # HH:MM:SS
                    hours, minutes, seconds = map(int, parts)
                    return dt.timedelta(hours=hours, minutes=minutes, seconds=seconds)
                elif len(parts) == 2:  # MM:SS
                    minutes, seconds = map(int, parts)
                    return dt.timedelta(minutes=minutes, seconds=seconds)
            # Try to parse as minutes
            try:
                minutes = float(duration_str)
                return dt.timedelta(minutes=minutes)
            except ValueError:
                pass
            return dt.timedelta(0)  # Default

        round_obj.duration = parse_duration(request.POST.get("duration"))
        round_obj.pitlane_open_after = parse_duration(
            request.POST.get("pitlane_open_after")
        )
        round_obj.pitlane_close_before = parse_duration(
            request.POST.get("pitlane_close_before")
        )
        round_obj.limit_time_min = parse_duration(request.POST.get("limit_time_min"))

        # Update other fields
        round_obj.change_lanes = int(request.POST.get("change_lanes"))
        round_obj.limit_time = request.POST.get("limit_time")
        round_obj.limit_method = request.POST.get("limit_method")
        round_obj.limit_value = int(request.POST.get("limit_value"))
        round_obj.required_changes = int(request.POST.get("required_changes"))

        # Handle weight_penalty JSON field
        weight_penalty_json = request.POST.get("weight_penalty", '[">=", [0, 0]]')
        try:
            weight_penalty = json.loads(weight_penalty_json)
            round_obj.weight_penalty = weight_penalty
        except json.JSONDecodeError:
            messages.error(request, "Invalid weight penalty format")
            return redirect("rounds_list")

        round_obj.save()
        messages.success(request, f"Round '{round_obj.name}' updated successfully")

    except Exception as e:
        messages.error(request, f"Error updating round: {str(e)}")

    return redirect("rounds_list")


@login_required
@user_passes_test(is_admin_user)
def create_driver(request):
    if request.method == "POST":
        form = DriverForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Driver added successfully!")
            return redirect("add_driver")  # Redirect to a page listing persons
    else:
        form = DriverForm()
    return render(request, "pages/add_driver.html", {"form": form})


@login_required
@user_passes_test(is_admin_user)
def create_team(request):
    if request.method == "POST":
        form = TeamForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Team added successfully!")
            return redirect("add_team")  # Redirect to a page listing persons
    else:
        form = TeamForm()
    return render(request, "pages/add_team.html", {"form": form})


def get_round_status(request):
    """Return the current round status as JSON"""
    # Get the current active round (you can use your existing method)
    end_date = dt.date.today()
    start_date = end_date - dt.timedelta(days=1)
    cround = Round.objects.filter(
        Q(start__date__range=[start_date, end_date]) & Q(ended__isnull=True)
    ).first()

    if not cround:
        return JsonResponse({"ready": False, "ongoing": False, "is_paused": True})

    return JsonResponse(
        {
            "ready": cround.ready,
            "ongoing": cround.ongoing,
            "is_paused": cround.is_paused,
        }
    )


def get_race_lanes(request):
    """Return the lanes for the current race"""
    # Get the current active round (use your existing method)
    end_date = dt.date.today()
    start_date = end_date - dt.timedelta(days=1)
    cround = Round.objects.filter(
        Q(start__date__range=[start_date, end_date]) & Q(ended__isnull=True)
    ).first()

    if not cround:
        return JsonResponse({"lanes": []})

    # Get lanes for this round
    lanes = ChangeLane.objects.filter(round=cround).values("id", "lane")

    return JsonResponse({"lanes": list(lanes)})


def driver_session_timer(request, driver_id):
    """Return the HTML for a driver's session timer"""
    driver = get_object_or_404(team_member, id=driver_id)

    # Load the timer template tag
    template = loader.get_template("layout/session_timer_snippet.html")
    context = {"member": driver}
    return HttpResponse(template.render(context, request))


def singleteam_view(request):
    """
    View to display a single team selected from a dropdown
    """
    end_date = dt.date.today()
    start_date = end_date - dt.timedelta(days=1)
    try:
        cround = Round.objects.filter(
            Q(start__date__range=[start_date, end_date]) & Q(ended__isnull=True)
        ).first()
    except:
        cround = None

    if cround:
        teams = (
            cround.round_team_set.all().select_related("team").order_by("team__number")
        )
        selected_team = None

        # Handle team selection from POST instead of GET
        if request.method == "POST":
            selected_team_id = request.POST.get("team_id")
            if selected_team_id and selected_team_id.isdigit():
                try:
                    selected_team = teams.get(team_id=selected_team_id)
                except round_team.DoesNotExist:
                    pass

        # Default to first team if none selected
        if not selected_team and teams.exists():
            selected_team = teams.first()

        context = {
            "round": cround,
            "teams": teams,
            "selected_team": selected_team,
        }
        return render(request, "pages/singleteam.html", context)
    else:
        return render(request, "pages/norace.html")
