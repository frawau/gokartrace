import datetime as dt
from django import forms
from .models import Round, championship_team, Person, team_member, round_team
from django.shortcuts import render, redirect
from django.views import View
from django.contrib import messages
from django.db.models import Exists, OuterRef, Value, BooleanField
from django.contrib.auth.decorators import login_required, user_passes_test
from .utils import is_admin_user
from django.utils.decorators import method_decorator


class TeamChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        # This will add a FontAwesome checkmark after the team name if is_round_team is True
        checkmark = " ⭐" if getattr(obj, "is_round_team", False) else ""
        return f"{str(obj)}{checkmark}"


class TeamSelectionForm(forms.Form):
    team = TeamChoiceField(
        queryset=championship_team.objects.none(), label="Select Team"
    )

    def __init__(self, *args, **kwargs):
        current_round = kwargs.pop("current_round", None)
        super().__init__(*args, **kwargs)
        if current_round:
            if current_round.ready:
                # Only show teams participating in this round
                self.fields["team"].queryset = (
                    championship_team.objects.filter(
                        championship=current_round.championship,
                        # Only include teams that have a corresponding round_team
                        round_team__round=current_round,
                    )
                    .annotate(
                        # Since we're only showing participating teams, they all have is_round_team=True
                        is_round_team=Value(True, output_field=BooleanField())
                    )
                    .order_by("number")
                )
            else:
                self.fields["team"].queryset = (
                    championship_team.objects.filter(
                        championship=current_round.championship
                    )
                    .annotate(
                        is_round_team=Exists(
                            round_team.objects.filter(
                                round=current_round, team_id=OuterRef("pk")
                            )
                        )
                    )
                    .order_by("number")
                )


class TeamMemberForm(forms.ModelForm):
    class Meta:
        model = team_member
        fields = ["driver", "manager", "weight"]
        widgets = {
            "driver": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "manager": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "weight": forms.NumberInput(attrs={"class": "form-control"}),
        }


class AddMemberForm(forms.Form):
    person = forms.ModelChoiceField(
        queryset=Person.objects.none(), label="Add New Member"
    )

    def __init__(self, *args, **kwargs):
        current_round = kwargs.pop("current_round", None)
        selected_team = kwargs.pop("selected_team", None)
        super().__init__(*args, **kwargs)

        if current_round and selected_team:
            # Get existing team members for this round and team
            existing_members = team_member.objects.filter(
                team__round=current_round,
            ).values_list("member_id", flat=True)

            # Exclude people who are already team members
            self.fields["person"].queryset = Person.objects.exclude(
                id__in=existing_members
            ).order_by("nickname")


@method_decorator(login_required, name="dispatch")
@method_decorator(user_passes_test(is_admin_user), name="dispatch")
class TeamMembersView(View):
    template_name = "pages/team_members.html"

    def get_current_round(self):
        # Get the current round (the next one starting today or later)
        return Round.objects.filter(start__gte=dt.date.today()).first()

    def get(self, request):
        current_round = self.get_current_round()
        if not current_round:
            messages.error(request, "No current championship round found.")
            return redirect("Home")

        team_form = TeamSelectionForm(current_round=current_round)
        add_member_form = AddMemberForm(current_round=current_round)

        context = {
            "current_round": current_round,
            "team_form": team_form,
            "add_member_form": add_member_form,
            "round_ready": current_round.ready,
        }
        return render(request, self.template_name, context)

    def post(self, request):
        current_round = self.get_current_round()
        if not current_round:
            messages.error(request, "No current championship round found.")
            return redirect("Home")

        # Check if it's a select_team action
        is_select_team = "select_team" in request.POST

        # Check round ready status
        if current_round.ready and not is_select_team:
            messages.error(
                request, "Race has started or is about to - no changes allowed."
            )
            return redirect(request.path)

        if not current_round.ready and "select_team" in request.POST:
            # First clean up empty round_team records
            empty_round_teams = round_team.objects.filter(
                round=current_round, team_member__isnull=True
            )
            deleted_count = empty_round_teams.delete()[0]
            if deleted_count:
                messages.info(
                    request, f"Cleaned up {deleted_count} empty team records."
                )

        if "select_team" in request.POST:
            team_form = TeamSelectionForm(request.POST, current_round=current_round)
            if team_form.is_valid():
                selected_team = team_form.cleaned_data["team"]
                return self.handle_team_selection(request, current_round, selected_team)

        elif "save_members" in request.POST:
            selected_team_id = request.POST.get("selected_team")
            if not selected_team_id:
                messages.error(request, "No team selected.")
                return redirect(request.path)

            try:
                selected_team = championship_team.objects.get(id=selected_team_id)
                return self.handle_member_updates(request, current_round, selected_team)
            except championship_team.DoesNotExist:
                messages.error(request, "Invalid team selected.")
                return redirect(request.path)

        elif "add_member" in request.POST:
            selected_team_id = request.POST.get("selected_team")
            if not selected_team_id:
                messages.error(request, "No team selected.")
                return redirect(request.path)

            try:
                selected_team = championship_team.objects.get(id=selected_team_id)
                return self.handle_add_member(request, current_round, selected_team)
            except championship_team.DoesNotExist:
                messages.error(request, "Invalid team selected.")
                return redirect(request.path)
        elif "remove_member" in request.POST:
            selected_team_id = request.POST.get("selected_team")
            member_id = request.POST.get("member_id")

            if not selected_team_id or not member_id:
                messages.error(request, "Invalid request.")
                return redirect(request.path)

            try:
                selected_team = championship_team.objects.get(id=selected_team_id)
                member = team_member.objects.get(id=member_id)
                member.delete()
                messages.success(request, "Member removed successfully.")
                return self.handle_team_selection(request, current_round, selected_team)
            except team_member.DoesNotExist:
                messages.error(request, "Member not found.")
                return redirect(request.path)

        messages.error(request, "Invalid action.")
        return redirect(request.path)

    def handle_team_selection(self, request, current_round, selected_team):
        # Get or create round_team for the selected team
        round_team_obj, created = round_team.objects.get_or_create(
            round=current_round, team=selected_team
        )

        # Get existing team members
        members = team_member.objects.filter(team=round_team_obj)

        # Create forms for each member
        member_forms = [
            TeamMemberForm(instance=member, prefix=f"member_{member.id}")
            for member in members
        ]

        # Create add member form with filtered queryset
        add_member_form = AddMemberForm(
            current_round=current_round, selected_team=selected_team
        )
        member_data = []
        for member, form in zip(members, member_forms):
            member_data.append({"member": member, "form": form})

        context = {
            "current_round": current_round,
            "selected_team": selected_team,
            "round_team_obj": round_team_obj,
            "member_data": member_data,
            "add_member_form": add_member_form,
            "team_form": TeamSelectionForm(
                initial={"team": selected_team.id}, current_round=current_round
            ),
        }
        return render(request, self.template_name, context)

    def handle_member_updates(self, request, current_round, selected_team):
        try:
            round_team_obj = round_team.objects.get(
                round=current_round, team=selected_team
            )
        except round_team.DoesNotExist:
            messages.error(request, "Team not found in this round.")
            return redirect(request.path)

        members = team_member.objects.filter(team=round_team_obj)
        all_valid = True

        # Process each member form
        for member in members:
            form = TeamMemberForm(
                request.POST, instance=member, prefix=f"member_{member.id}"
            )
            if form.is_valid():
                form.save()
            else:
                all_valid = False

        if all_valid:
            messages.success(request, "Team members updated successfully.")
        else:
            messages.error(request, "There were errors in some member updates.")

        return self.handle_team_selection(request, current_round, selected_team)

    def handle_add_member(self, request, current_round, selected_team):
        add_member_form = AddMemberForm(
            request.POST, current_round=current_round, selected_team=selected_team
        )

        if add_member_form.is_valid():
            person = add_member_form.cleaned_data["person"]

            # Get or create round_team for the selected team
            round_team_obj, created = round_team.objects.get_or_create(
                round=current_round, team=selected_team
            )

            # Create new team member
            team_member.objects.create(
                team=round_team_obj, member=person, driver=True, manager=False, weight=0
            )

            messages.success(request, f"{person.nickname} added to the team.")
        else:
            messages.error(request, "Invalid selection for new member.")

        return self.handle_team_selection(request, current_round, selected_team)
