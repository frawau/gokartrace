# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""
import datetime as dt
import json
import re
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_http_methods, require_POST
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
from django.db import IntegrityError
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
    Session,
)
from .serializers import ChangeLaneSerializer
from .utils import datadecode, is_admin_user
from .forms import DriverForm, TeamForm, JoinChampionshipForm
from django.template import loader
from django.db import models
from django_countries import countries


def current_round():
    end_date = dt.date.today()
    start_date = end_date - dt.timedelta(days=1)
    return Round.objects.filter(
        Q(start__date__range=[start_date, end_date]) & Q(ended__isnull=True)
    ).first()


def active_round():
    end_date = dt.date.today()
    start_date = end_date - dt.timedelta(days=1)
    return Round.objects.filter(
        Q(start__date__gte=start_date) & Q(ended__isnull=True)
    ).first()


def index(request):
    # Page from the theme
    button_matrix = [
        [
            {"label": "Team Carousel", "url": "/teamcarousel/"},
            {"label": "Driver's Queue", "url": "/pending_drivers/"},
            {"label": "Drivers on Track", "url": "/driverontrack/"},
        ],
        [
            {"label": "Monitor One Team", "url": "/singleteam/"},
            {"label": "Monitor One Driver", "url": "/onedriver/"},
            {"label": "All Pit Lanes", "url": "/all_pitlanes/"},
        ],
    ]
    cround = current_round()
    return render(
        request, "pages/index.html", {"round": cround, "buttons": button_matrix}
    )


def team_carousel(request):
    cround = current_round()

    return render(request, "pages/teamcarousel.html", {"round": cround})


def get_team_card(request):
    cround = current_round()
    team_id = request.GET.get("team_id")
    round_team_instance = get_object_or_404(round_team, pk=team_id)
    assert cround == round_team_instance.round
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
    cround = current_round()
    change_lane = get_object_or_404(ChangeLane, round=cround, lane=lane_number)
    return render(request, "layout/changelane_info.html", {"change_lane": change_lane})


def changelane_detail(request, lane_number):
    cround = current_round()
    change_lane = get_object_or_404(ChangeLane, round=cround, lane=lane_number)
    return render(
        request, "layout/changelane_small_detail.html", {"change_lane": change_lane}
    )


def update_change_lane(request, lane_number):
    cround = current_round()
    change_lane = get_object_or_404(ChangeLane, round=cround, lane=lane_number)
    if change_lane.open == True:
        change_lane.next_driver()  # This is the function that updates the driver.
    change_lane.save()
    return render(request, "layout/changelane_info.html", {"change_lane": change_lane})


def changedriver_info(request):
    try:
        cround = current_round()
        change_lanes = ChangeLane.objects.filter(round=cround, open=True).order_by(
            "lane"
        )
        return render(
            request, "layout/changedriver_info.html", {"change_lanes": change_lanes}
        )
    except:
        return render(request, "pages/norace.html")


def all_pitlanes(request):
    try:
        cround = current_round()
        change_lanes = ChangeLane.objects.filter(round=cround).order_by("lane")
        return render(
            request,
            "pages/all_pitlanes.html",
            {"change_lanes": change_lanes, "round": cround},
        )
    except:
        return render(request, "pages/norace.html")


def is_race_director(user):
    return user.is_authenticated and user.groups.filter(name="Race Director").exists()


@login_required
@user_passes_test(is_race_director)
def racecontrol(request):
    cround = current_round()
    try:
        lanes = cround.change_lanes

        # Get all sessions that are registered but not started or ended
        pending_sessions = (
            Session.objects.filter(
                round=cround,
                register__isnull=False,
                start__isnull=True,
                end__isnull=True,
            )
            .select_related(
                "driver", "driver__team", "driver__member", "driver__team__team"
            )
            .order_by("register")
        )  # Order by registration time

        # For each session, get the team's completed sessions count
        for session in pending_sessions:
            completed_count = Session.objects.filter(
                driver__team=session.driver.team, end__isnull=False
            ).count()

            # Add as property to the session object
            session.team_completed_count = completed_count
        return render(
            request,
            "pages/racecontrol.html",
            {"round": cround, "lanes": lanes, "pending_sessions": pending_sessions},
        )
    except:
        return render(request, "pages/norace.html")


@login_required
@user_passes_test(is_race_director)
def preracecheck(request):
    cround = current_round()
    res = cround.pre_race_check()
    if res:
        return JsonResponse({"result": False, "error": res})

    return JsonResponse({"result": True})


@login_required
@user_passes_test(is_race_director)
def race_start(request):
    cround = current_round()
    cround.start_race()
    return JsonResponse({"result": True})


@login_required
@user_passes_test(is_race_director)
def falsestart(request):
    cround = current_round()
    cround.false_start()
    return JsonResponse({"result": True})


@login_required
@user_passes_test(is_race_director)
def racepaused(request):
    cround = current_round()
    cround.pause_race()
    return JsonResponse({"result": True})


@login_required
@user_passes_test(is_race_director)
def racerestart(request):
    cround = current_round()
    cround.restart_race()
    return JsonResponse({"result": True})


@login_required
@user_passes_test(is_race_director)
def falserestart(request):
    cround = current_round()
    cround.false_restart()
    return JsonResponse({"result": True})


@login_required
@user_passes_test(is_race_director)
def endofrace(request):
    cround = current_round()
    errs = cround.end_race()
    return JsonResponse({"result": True})


@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
@authentication_classes([])
def agent_login(request):
    """
    API endpoint for user login and token generation.
    """
    cround = current_round()
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
        cround = current_round()
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
        cround = current_round()
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
    rounds = Round.objects.filter(championship=champ, ready=False).order_by("start")
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
        cround = Round.objects.get(pk=round_id)

        # Ensure weight_penalty is properly formatted
        if not cround.weight_penalty:
            cround.weight_penalty = [">=", [0, 0]]

        # If it's a string, try to parse it
        if isinstance(cround.weight_penalty, str):
            try:
                cround.weight_penalty = json.loads(cround.weight_penalty)
            except json.JSONDecodeError:
                cround.weight_penalty = [">=", [0, 0]]

        # Convert to JSON string for template
        context = {
            "round": cround,
        }
        return render(request, "layout/roundedit.html", context)
    except Round.DoesNotExist:
        return HttpResponse("Round not found")


@login_required
@user_passes_test(is_admin_user)
@require_http_methods(["POST"])
def update_round(request, round_id):
    """Handle the form submission to update a round"""
    cround = get_object_or_404(Round, pk=round_id)
    if cround.ready:
        messages.error(request, "This round can no longer be modified.")
    else:
        try:
            # Update basic fields
            cround.name = request.POST.get("name")
            cround.start = request.POST.get("start")

            # Parse duration strings
            def parse_duration(duration_str):
                if ":" in duration_str:
                    parts = duration_str.split(":")
                    if len(parts) == 3:  # HH:MM:SS
                        hours, minutes, seconds = map(int, parts)
                        return dt.timedelta(
                            hours=hours, minutes=minutes, seconds=seconds
                        )
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

            cround.duration = parse_duration(request.POST.get("duration"))
            cround.pitlane_open_after = parse_duration(
                request.POST.get("pitlane_open_after")
            )
            cround.pitlane_close_before = parse_duration(
                request.POST.get("pitlane_close_before")
            )
            cround.limit_time_min = parse_duration(request.POST.get("limit_time_min"))

            # Update other fields
            cround.change_lanes = int(request.POST.get("change_lanes"))
            cround.limit_time = request.POST.get("limit_time")
            cround.limit_method = request.POST.get("limit_method")
            cround.limit_value = int(request.POST.get("limit_value"))
            cround.required_changes = int(request.POST.get("required_changes"))

            # Handle weight_penalty JSON field
            weight_penalty_json = request.POST.get("weight_penalty", '[">=", [0, 0]]')
            try:
                weight_penalty = json.loads(weight_penalty_json)
                cround.weight_penalty = weight_penalty
            except json.JSONDecodeError:
                messages.error(request, "Invalid weight penalty format")
                return redirect("rounds_list")

            cround.save()
            messages.success(request, f"Round '{cround.name}' updated successfully")

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
            team = form.save()

            championship = form.cleaned_data.get("championship")
            team_number = form.cleaned_data.get("team_number")

            if championship and team_number:
                try:
                    championship_team.objects.create(
                        championship=championship, team=team, number=team_number
                    )
                except IntegrityError:
                    # Handle the rare case where someone else took the number
                    # between form validation and saving
                    form.add_error(
                        "team_number", "This team number is no longer available."
                    )
                    team.delete()  # Clean up the team if registration failed
                    return render(request, "pages/add_team.html", {"form": form})
            messages.success(request, "Team added successfully!")
            return redirect("add_team")  # Redirect to a page listing persons
    else:
        form = TeamForm()
    return render(request, "pages/add_team.html", {"form": form})


def get_round_status(request):
    """Return the current round status as JSON"""
    # Get the current active round (you can use your existing method)
    cround = current_round()

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
    cround = current_round()

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
    try:
        cround = current_round()
    except:
        cround = None

    if cround:
        # Always get all teams for the dropdown
        teams = cround.round_team_set.all().order_by("team__number")

        # Handle team selection from POST
        selected_team = None
        if request.method == "POST":
            selected_team_id = request.POST.get("team_id")
            if selected_team_id and selected_team_id.isdigit():
                try:
                    # Get just the specific round_team by ID
                    selected_team = cround.round_team_set.get(id=selected_team_id)
                except round_team.DoesNotExist:
                    selected_team = None
        # For initial page load, optionally default to first team
        elif teams.exists():
            selected_team = teams.first()

        context = {
            "round": cround,
            "teams": teams,
            "selected_team": selected_team,
        }
        return render(request, "pages/singleteam.html", context)
    else:
        return render(request, "pages/norace.html")


def pending_drivers(request):
    """View to display all pending sessions for the current round"""
    try:
        cround = current_round()
    except:
        cround = None

    # If no round is found
    if not cround:
        return render(request, "pages/pending_drivers.html", {"round": None})

    # Get all sessions that are registered but not started or ended
    pending_sessions = (
        Session.objects.filter(
            round=cround,
            register__isnull=False,
            start__isnull=True,
            end__isnull=True,
        )
        .select_related(
            "driver", "driver__team", "driver__member", "driver__team__team"
        )
        .order_by("register")
    )  # Order by registration time

    # For each session, get the team's completed sessions count
    for session in pending_sessions:
        completed_count = Session.objects.filter(
            driver__team=session.driver.team, end__isnull=False
        ).count()

        # Add as property to the session object
        session.team_completed_count = completed_count

    context = {
        "round": cround,
        "pending_sessions": pending_sessions,
    }

    return render(request, "pages/pending_drivers.html", context)


def driver_info_api(request, driver_id):
    """API endpoint to get driver info for the pending sessions table"""
    driver = get_object_or_404(team_member, pk=driver_id)

    # Return the needed information for the front-end
    return JsonResponse(
        {
            "driver_id": driver.id,
            "team_id": driver.team.id,
            "team_number": driver.team.team.number,
            "nickname": driver.member.nickname,
        }
    )


@login_required
@user_passes_test(is_admin_user)
def join_championship_view(request):
    if request.method == "POST":
        form = JoinChampionshipForm(request.POST)
        if form.is_valid():
            championship = form.cleaned_data["championship"]
            team_id = form.cleaned_data["team"]
            number = form.cleaned_data["number"]

            try:
                team = Team.objects.get(id=team_id)
                championship_team.objects.create(
                    championship=championship, team=team, number=number
                )
                # Store success message in session
                request.session[
                    "success_message"
                ] = f"Successfully added {team.name} to {championship.name} with number {number}!"
                return redirect("join_championship")
            except Team.DoesNotExist:
                form.add_error("team", "Selected team does not exist.")
            except IntegrityError:
                form.add_error(
                    None, "This team or number is already taken in this championship."
                )
    else:
        form = JoinChampionshipForm()

        # Get and clear success message from session
        success_message = request.session.pop("success_message", None)

    return render(
        request,
        "pages/join_championship.html",
        {"form": form, "success_message": success_message},
    )


@login_required
@user_passes_test(is_admin_user)
@require_POST
def get_available_teams(request):
    print(f"Available teams with {request}")
    championship_id = request.POST.get("championship_id")
    if not championship_id:
        return JsonResponse({"teams": []})

    joined_teams = championship_team.objects.filter(
        championship_id=championship_id
    ).values_list("team_id", flat=True)

    available_teams = Team.objects.exclude(id__in=joined_teams).values("id", "name")

    return JsonResponse({"teams": list(available_teams)})


@login_required
@user_passes_test(is_admin_user)
@require_POST
def get_available_numbers(request):
    print(f"Available number with {request}")
    championship_id = request.POST.get("championship_id")
    if not championship_id:
        return JsonResponse({"numbers": []})

    used_numbers = championship_team.objects.filter(
        championship_id=championship_id
    ).values_list("number", flat=True)

    available_numbers = [str(i) for i in range(1, 100) if i not in used_numbers]

    return JsonResponse({"numbers": available_numbers})


def round_info(request):
    # Get all rounds sorted by date
    rounds = Round.objects.all().order_by("start")

    # Find closest round to today
    selected_round_id = request.GET.get("round_id")
    if not selected_round_id:
        today = dt.date.today()
        closest_round = rounds.filter(start__date__gte=today).first()
        if not closest_round:
            closest_round = rounds.last()
        selected_round_id = closest_round.id if closest_round else None

    selected_round = None
    round_teams = []

    if selected_round_id:
        selected_round = Round.objects.get(id=selected_round_id)
        round_teams = round_team.objects.filter(round=selected_round)

        # For each team, preload related members and their sessions
        for rt in round_teams:
            # Get the completed sessions count
            rt.completed_sessions_count = Session.objects.filter(
                round=selected_round, driver__team=rt, end__isnull=False
            ).count()

            # Get all team members
            rt.members = team_member.objects.filter(team=rt)

            # For each member, preload their sessions
            for member in rt.members:
                member.sessions_count = Session.objects.filter(
                    driver=member, end__isnull=False
                ).count()

                member.all_sessions = Session.objects.filter(driver=member).order_by(
                    "start"
                )

    context = {
        "rounds": rounds,
        "selected_round": selected_round,
        "selected_round_id": int(selected_round_id) if selected_round_id else None,
        "round_teams": round_teams,
    }
    return render(request, "pages/round_info.html", context)


def all_drivers_view(request):
    # Get all championships with end date after today
    today = dt.date.today()
    championships = Championship.objects.filter(end__gte=today).order_by("-end")

    selected_championship_id = request.GET.get("championship")
    selected_championship = None
    rounds = []
    persons = []

    if selected_championship_id:
        selected_championship = get_object_or_404(
            Championship, id=selected_championship_id
        )
        rounds = Round.objects.filter(championship=selected_championship).order_by(
            "start"
        )

        # Get all persons who are team members in any round of this championship
        persons = Person.objects.filter(
            team_member__team__round__championship=selected_championship
        ).distinct()

        # For each person, get their team information for each round
        for person in persons:
            person.teams = []
            for round_obj in rounds:
                team_members = team_member.objects.filter(
                    team__round=round_obj, member=person
                ).select_related("team__team")

                for tm in team_members:
                    person.teams.append(
                        {
                            "round_id": round_obj.id,
                            "number": tm.team.team.number,
                            "name": tm.team.team.team.name,
                        }
                    )

    context = {
        "championships": championships,
        "selected_championship": selected_championship,
        "rounds": rounds,
        "persons": persons,
    }

    return render(request, "pages/alldriver.html", context)


def all_teams_view(request):
    # Get all championships that haven't ended yet
    championships = Championship.objects.filter(end__gte=dt.date.today()).order_by(
        "-end"
    )

    selected_championship = None
    rounds = []
    teams = []

    championship_id = request.GET.get("championship")
    if championship_id:
        selected_championship = get_object_or_404(Championship, id=championship_id)
        rounds = Round.objects.filter(championship=selected_championship).order_by(
            "start"
        )

        # Get all teams and their round participation
        teams = (
            Team.objects.annotate(
                championship_number=models.Case(
                    models.When(
                        championship_team__championship=selected_championship,
                        then=models.F("championship_team__number"),
                    ),
                    default=models.Value(
                        999
                    ),  # Teams without a number will be sorted last
                    output_field=models.IntegerField(),
                )
            )
            .prefetch_related(
                "championship_team_set",
                "championship_team_set__round_team_set",
                "championship_team_set__round_team_set__round",
            )
            .order_by("championship_number")
        )

    context = {
        "championships": championships,
        "selected_championship": selected_championship,
        "rounds": rounds,
        "teams": teams,
    }

    return render(request, "pages/allteams.html", context)


@login_required
@user_passes_test(is_admin_user)
def edit_driver_view(request):
    if request.method == 'POST':
        try:
            driver_id = request.POST.get('driver_id')
            driver = get_object_or_404(Person, id=driver_id)
            
            # Update driver fields
            driver.surname = request.POST.get('surname')
            driver.firstname = request.POST.get('firstname')
            driver.nickname = request.POST.get('nickname')
            driver.gender = request.POST.get('gender')
            driver.birthdate = request.POST.get('birthdate')
            driver.country = request.POST.get('country')
            driver.email = request.POST.get('email') or None
            
            # Handle mugshot upload
            if 'mugshot' in request.FILES:
                driver.mugshot = request.FILES['mugshot']
            
            driver.save()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    # GET request - show the form
    drivers = Person.objects.all().order_by('nickname')
    countries_list = list(countries)
    
    context = {
        'drivers': drivers,
        'countries': countries_list,
    }
    return render(request, 'pages/edit_driver.html', context)

@login_required
@user_passes_test(is_admin_user)
def edit_team_view(request):
    if request.method == 'POST':
        try:
            team_id = request.POST.get('team_id')
            team = get_object_or_404(Team, id=team_id)
            
            # Update team fields
            team.name = request.POST.get('name')
            
            # Handle logo upload
            if 'logo' in request.FILES:
                team.logo = request.FILES['logo']
            
            team.save()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    # GET request - show the form
    teams = Team.objects.all().order_by('name')
    
    context = {
        'teams': teams,
    }
    return render(request, 'pages/edit_team.html', context)

@login_required
@user_passes_test(is_admin_user)
def create_championship_view(request):
    if request.method == 'POST':
        try:
            name = request.POST.get('name')
            year = int(request.POST.get('year'))
            num_rounds = int(request.POST.get('rounds'))
            
            # Create championship with start and end dates
            start_date = dt.date(year, 1, 1)
            end_date = dt.date(year, 12, 31)
            
            championship = Championship.objects.create(
                name=name,
                start=start_date,
                end=end_date
            )
            
            # Create rounds
            # Calculate days between rounds to spread them evenly
            days_between_rounds = (end_date - start_date).days // (num_rounds + 1)
            current_date = start_date + dt.timedelta(days=days_between_rounds)
            
            for i in range(num_rounds):
                round_start = dt.datetime.combine(current_date, dt.time(18, 0))  # 18:00
                Round.objects.create(
                    championship=championship,
                    name=f"Round {i + 1}",
                    start=round_start,
                    duration=dt.timedelta(hours=4),
                    ready=False
                )
                current_date += dt.timedelta(days=days_between_rounds)
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    # GET request - show the form
    current_year = dt.date.today().year
    context = {
        'current_year': current_year,
    }
    return render(request, 'pages/create_championship.html', context)

@login_required
@user_passes_test(is_admin_user)
def edit_championship_view(request):
    if request.method == 'POST':
        try:
            championship_id = request.POST.get('championship_id')
            championship = get_object_or_404(Championship, id=championship_id)
            
            # Handle round management
            action = request.POST.get('action')
            
            # Only update championship fields if this is not a round management action
            if not action:
                # Update championship fields
                championship.name = request.POST.get('name')
                year_str = request.POST.get('year')
                if year_str:
                    year = int(year_str)
                    # Update start and end dates
                    championship.start = dt.date(year, 1, 1)
                    championship.end = dt.date(year, 12, 31)
                
                championship.save()
            
            if action == 'add_round':
                # Add a new round
                existing_rounds = Round.objects.filter(championship=championship, ready=False).order_by('start')
                if existing_rounds.exists():
                    # Calculate new round date based on last round
                    last_round = existing_rounds.last()
                    new_start = last_round.start + dt.timedelta(days=7)  # 1 week after last round
                else:
                    # First round - start 1 week after championship start
                    new_start = dt.datetime.combine(championship.start + dt.timedelta(days=7), dt.time(18, 0))
                
                Round.objects.create(
                    championship=championship,
                    name=f"Round {existing_rounds.count() + 1}",
                    start=new_start,
                    duration=dt.timedelta(hours=4),
                    ready=False
                )
                
            elif action == 'delete_round':
                # Delete the latest round (ready=False only)
                latest_round = Round.objects.filter(championship=championship, ready=False).order_by('-start').first()
                if latest_round:
                    latest_round.delete()
                    
            elif action == 'set_rounds':
                # Set specific number of rounds
                num_rounds_str = request.POST.get('num_rounds', '0')
                target_rounds = int(num_rounds_str) if num_rounds_str else 0
                ready_true_rounds = list(Round.objects.filter(championship=championship, ready=True).order_by('start'))
                ready_false_rounds = list(Round.objects.filter(championship=championship, ready=False).order_by('start'))
                ready_true_count = len(ready_true_rounds)
                ready_false_count = len(ready_false_rounds)
                
                if target_rounds < ready_true_count:
                    return JsonResponse({'success': False, 'error': f'Cannot set number of rounds less than the number of started/completed rounds ({ready_true_count}).'})
                
                desired_ready_false = target_rounds - ready_true_count
                current_ready_false = ready_false_count

                # Find the highest round number among all rounds (ready or not)
                round_num_re = re.compile(r'Round (\d+)')
                all_rounds = list(Round.objects.filter(championship=championship).order_by('start'))
                max_round_num = 0
                for rnd in all_rounds:
                    m = round_num_re.match(rnd.name)
                    if m:
                        n = int(m.group(1))
                        if n > max_round_num:
                            max_round_num = n
                next_round_num = max_round_num + 1

                if desired_ready_false == 0:
                    # Delete all ready=False rounds
                    Round.objects.filter(championship=championship, ready=False).delete()
                elif desired_ready_false > current_ready_false:
                    # Add rounds
                    existing_rounds = Round.objects.filter(championship=championship).order_by('start')
                    if existing_rounds.exists():
                        last_round = existing_rounds.last()
                        base_start = last_round.start
                    else:
                        base_start = dt.datetime.combine(championship.start + dt.timedelta(days=7), dt.time(18, 0))
                    for i in range(desired_ready_false - current_ready_false):
                        new_start = base_start + dt.timedelta(days=7 * (i + 1))
                        Round.objects.create(
                            championship=championship,
                            name=f"Round {next_round_num + i}",
                            start=new_start,
                            duration=dt.timedelta(hours=4),
                            ready=False
                        )
                elif desired_ready_false < current_ready_false:
                    # Delete rounds (always delete the latest ones, only ready=False)
                    rounds_to_delete = current_ready_false - desired_ready_false
                    latest_rounds = Round.objects.filter(championship=championship, ready=False).order_by('-start')[:rounds_to_delete]
                    for round_obj in latest_rounds:
                        round_obj.delete()
                    # After deletion, re-number remaining ready=False rounds
                    # Find the highest round number among all rounds again
                    all_rounds = list(Round.objects.filter(championship=championship).order_by('start'))
                    max_round_num = 0
                    for rnd in all_rounds:
                        m = round_num_re.match(rnd.name)
                        if m:
                            n = int(m.group(1))
                            if n > max_round_num:
                                max_round_num = n
                    next_round_num = max_round_num + 1
                    remaining_false = list(Round.objects.filter(championship=championship, ready=False).order_by('start'))
                    for idx, rnd in enumerate(remaining_false):
                        rnd.name = f"Round {next_round_num + idx}"
                        rnd.save()
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    # GET request - show the form
    championships = Championship.objects.all().order_by('-start')
    
    context = {
        'championships': championships,
    }
    return render(request, 'pages/edit_championship.html', context)

@login_required
@user_passes_test(is_admin_user)
def edit_round_view(request):
    if request.method == 'POST':
        try:
            round_id = request.POST.get('round_id')
            round_obj = get_object_or_404(Round, id=round_id)
            
            # Update round fields
            round_obj.name = request.POST.get('name')
            round_obj.start = request.POST.get('start')
            
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
                return dt.timedelta(0)

            round_obj.duration = parse_duration(request.POST.get('duration'))
            round_obj.pitlane_open_after = parse_duration(request.POST.get('pitlane_open_after'))
            round_obj.pitlane_close_before = parse_duration(request.POST.get('pitlane_close_before'))
            
            # Update other fields
            round_obj.change_lanes = int(request.POST.get('change_lanes'))
            round_obj.limit_time = request.POST.get('limit_time')
            round_obj.limit_value = int(request.POST.get('limit_value'))
            round_obj.required_changes = int(request.POST.get('required_changes'))
            
            # Handle weight penalty JSON field
            weight_penalty_json = request.POST.get('weight_penalty', '[">=", [0, 0]]')
            try:
                weight_penalty = json.loads(weight_penalty_json)
                round_obj.weight_penalty = weight_penalty
            except json.JSONDecodeError:
                return JsonResponse({'success': False, 'error': 'Invalid weight penalty format'})
            
            round_obj.save()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    # GET request - show the form
    championships = Championship.objects.all().order_by('-start')
    
    context = {
        'championships': championships,
    }
    return render(request, 'pages/edit_round.html', context)

@login_required
@user_passes_test(is_admin_user)
def get_championship_rounds(request, championship_id):
    """API endpoint to get rounds for a championship"""
    try:
        championship = get_object_or_404(Championship, id=championship_id)
        rounds = Round.objects.filter(championship=championship, ready=False).order_by('start')
        
        def format_duration(td):
            """Format timedelta as HH:MM:SS with leading zeros"""
            total_seconds = int(td.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
        def format_minutes_seconds(td):
            """Format timedelta as MM:SS with leading zeros"""
            total_seconds = int(td.total_seconds())
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            return f"{minutes:02d}:{seconds:02d}"
        
        rounds_data = []
        for round_obj in rounds:
            rounds_data.append({
                'id': round_obj.id,
                'name': round_obj.name,
                'start': round_obj.start.isoformat(),
                'duration': format_duration(round_obj.duration),
                'change_lanes': round_obj.change_lanes,
                'pitlane_open_after': format_minutes_seconds(round_obj.pitlane_open_after),
                'pitlane_close_before': format_minutes_seconds(round_obj.pitlane_close_before),
                'limit_time': round_obj.limit_time,
                'limit_method': round_obj.limit_method,
                'limit_value': round_obj.limit_value,
                'limit_time_min': format_minutes_seconds(round_obj.limit_time_min),
                'required_changes': round_obj.required_changes,
                'weight_penalty': round_obj.weight_penalty or [">=", [0, 0]]
            })
        
        return JsonResponse(rounds_data, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
