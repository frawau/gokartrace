import datetime as dt
from django import forms
from django.forms import inlineformset_factory
from .models import Team, team_member, Person, round_team, Round, championship_team
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import render, redirect

class TeamSelectionForm(forms.Form):
    team = forms.ModelChoiceField(queryset=Team.objects.all())

class TeamMemberForm(forms.ModelForm):
    class Meta:
        model = team_member
        fields = ['driver', 'manager', 'weight']

TeamMemberFormSet = inlineformset_factory(
    round_team, team_member, form=TeamMemberForm, extra=0, can_delete=True
)

class AddTeamMemberForm(forms.Form):
    member = forms.ModelChoiceField(queryset=Person.objects.none())  # Initial queryset is empty

    def __init__(self, *args, **kwargs):
        round_instance = kwargs.pop('round_instance', None)
        team_instance = kwargs.pop('team_instance', None)
        super().__init__(*args, **kwargs)
        if round_instance and team_instance:
            existing_members = team_member.objects.filter(team__round=round_instance, team__team=team_instance).values_list('member', flat=True)
            self.fields['member'].queryset = Person.objects.exclude(id__in=existing_members)

def get_team_member_form(request, round_instance):
    if request.method == 'POST':
        team_form = TeamSelectionForm(request.POST)
        if team_form.is_valid():
            selected_team = team_form.cleaned_data['team']
            try:
                championship_team_instance = championship_team.objects.get(
                    championship=round_instance.championship,
                    team=selected_team
                )
                round_team_instance = round_team.objects.get(round=round_instance, team=championship_team_instance)
                formset = TeamMemberFormSet(request.POST, instance=round_team_instance, prefix='members')
            except ObjectDoesNotExist:
                championship_team_instance = championship_team.objects.filter(championship=round_instance.championship, team=selected_team).first()
                round_team_instance = None
                formset = TeamMemberFormSet(request.POST, instance=None, prefix='members')

            add_member_form = AddTeamMemberForm(request.POST, round_instance=round_instance, team_instance=selected_team)
            return team_form, formset, add_member_form, selected_team, round_team_instance

        else:
            return team_form, None, None, None, None

    else:
        team_form = TeamSelectionForm()
        return team_form, None, None, None, None

def process_team_member(request, round_instance, selected_team, round_team_instance):
    if request.method == 'POST':
        championship_team_instance = championship_team.objects.get(championship=round_instance.championship, team=selected_team)
        try:
            round_team_instance = round_team.objects.get(round=round_instance, team=championship_team_instance)
            formset = TeamMemberFormSet(request.POST, instance=round_team_instance, prefix='members')
        except ObjectDoesNotExist:
            formset = TeamMemberFormSet(request.POST, instance=None, prefix='members')

        add_member_form = AddTeamMemberForm(request.POST, round_instance=round_instance, team_instance=selected_team)

        if formset.is_valid() and add_member_form.is_valid():
            if round_team_instance is None:
                round_team_instance = round_team.objects.create(round=round_instance, team=championship_team_instance)
            formset.instance = round_team_instance
            formset.save()

            if add_member_form.cleaned_data['member']:
                team_member.objects.create(
                    team=round_team_instance,
                    member=add_member_form.cleaned_data['member'],
                    driver=False,
                    manager=False,
                    weight=0
                )
            return True
        else:
            return False
    else:
        return False

def get_round():
    return Round.objects.filter(start__gte=dt.date.today()).first()

def view_team_member(request):
    round_instance = get_round()

    if not round_instance:
        return render(request, 'pages/norace.html')

    team_form, formset, add_member_form, selected_team, round_team_instance = get_team_member_form(request, round_instance)

    if request.method == 'POST' and selected_team:
        if process_team_member(request, round_instance, selected_team, round_team_instance):
            return redirect('Home')

    context = {
        'team_form': team_form,
        'formset': formset,
        'add_member_form': add_member_form,
        'selected_team': selected_team,
        'round': round_instance,
    }

    return render(request, 'pages/team_members.html', context)
