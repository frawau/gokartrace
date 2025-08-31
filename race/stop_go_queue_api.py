# Stop & Go Queue Management API Endpoints
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.db import models
import json
import datetime as dt

from .models import Round, RoundPenalty, StopAndGoQueue, ChampionshipPenalty


@login_required
@csrf_exempt  
def get_stop_go_queue_status(request, round_id):
    """API endpoint to get current Stop & Go queue status."""
    try:
        round_obj = get_object_or_404(Round, id=round_id)
        
        # Get active penalty
        active_penalty = StopAndGoQueue.get_active_penalty(round_id)
        active_data = None
        if active_penalty:
            active_data = {
                "queue_id": active_penalty.id,
                "penalty_id": active_penalty.round_penalty.id,
                "team_number": active_penalty.round_penalty.offender.team.number,
                "team_name": active_penalty.round_penalty.offender.team.team.name,
                "penalty_name": active_penalty.round_penalty.penalty.penalty.name,
                "value": active_penalty.round_penalty.value,
                "activated_at": active_penalty.activated_at.isoformat() if active_penalty.activated_at else None
            }
        
        # Get queued penalties
        queued_penalties = StopAndGoQueue.objects.filter(
            round_id=round_id,
            status='queued'
        ).order_by('queue_position', 'created_at')
        
        queue_data = []
        for penalty in queued_penalties:
            queue_data.append({
                "queue_id": penalty.id,
                "penalty_id": penalty.round_penalty.id,
                "team_number": penalty.round_penalty.offender.team.number,
                "team_name": penalty.round_penalty.offender.team.team.name,
                "penalty_name": penalty.round_penalty.penalty.penalty.name,
                "value": penalty.round_penalty.value,
                "queue_position": penalty.queue_position
            })
        
        return JsonResponse({
            "success": True,
            "active_penalty": active_data,
            "queue": queue_data,
            "queue_count": len(queue_data)
        })
        
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@login_required
@csrf_exempt
def cancel_stop_go_penalty(request):
    """API endpoint to cancel an active Stop & Go penalty."""
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            queue_id = data.get("queue_id")
            
            queue_entry = get_object_or_404(StopAndGoQueue, id=queue_id)
            
            # Can only cancel active penalties
            if queue_entry.status != 'active':
                return JsonResponse({
                    "success": False, 
                    "error": "Can only cancel active penalties"
                }, status=400)
            
            # Cancel the penalty
            queue_entry.cancel()
            
            # Activate next penalty in queue after a delay
            next_penalty = StopAndGoQueue.get_next_in_queue(queue_entry.round.id)
            if next_penalty:
                # TODO: Add 10-second delay mechanism here
                next_penalty.activate()
            
            return JsonResponse({
                "success": True,
                "message": "Penalty cancelled successfully",
                "next_penalty_activated": next_penalty.id if next_penalty else None
            })
            
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)}, status=400)
    
    return JsonResponse({"error": "Only POST method allowed"}, status=405)


@login_required
@csrf_exempt
def delay_stop_go_penalty(request):
    """API endpoint to delay an active Stop & Go penalty (move to end of queue)."""
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            queue_id = data.get("queue_id")
            
            queue_entry = get_object_or_404(StopAndGoQueue, id=queue_id)
            
            # Can only delay active penalties
            if queue_entry.status != 'active':
                return JsonResponse({
                    "success": False, 
                    "error": "Can only delay active penalties"
                }, status=400)
            
            # Check if we should create an "ignoring s&g" penalty
            create_ignoring_penalty = False
            ignoring_penalty = None
            
            try:
                # Look for "ignoring s&g" penalty in the championship
                championship = queue_entry.round.championship
                ignoring_penalty = ChampionshipPenalty.objects.filter(
                    championship=championship,
                    penalty__name__icontains="ignoring"
                ).first()
                
                if ignoring_penalty:
                    create_ignoring_penalty = True
            except:
                pass  # If no ignoring penalty exists, just delay without creating one
            
            # Delay the current penalty (moves to end of queue)
            queue_entry.delay()
            
            # Create "ignoring s&g" penalty if found
            ignoring_penalty_id = None
            if create_ignoring_penalty and ignoring_penalty:
                ignoring_round_penalty = RoundPenalty.objects.create(
                    round=queue_entry.round,
                    offender=queue_entry.round_penalty.offender,
                    victim=queue_entry.round_penalty.victim,
                    penalty=ignoring_penalty,
                    value=ignoring_penalty.value,
                    imposed=dt.datetime.now(),
                    served=None
                )
                ignoring_penalty_id = ignoring_round_penalty.id
            
            # Activate next penalty in queue after a delay
            next_penalty = StopAndGoQueue.get_next_in_queue(queue_entry.round.id)
            if next_penalty:
                # TODO: Add 10-second delay mechanism here
                next_penalty.activate()
            
            return JsonResponse({
                "success": True,
                "message": "Penalty delayed and moved to end of queue",
                "delayed_penalty_id": queue_entry.id,
                "next_penalty_activated": next_penalty.id if next_penalty else None,
                "ignoring_penalty_created": ignoring_penalty_id is not None,
                "ignoring_penalty_id": ignoring_penalty_id
            })
            
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)}, status=400)
    
    return JsonResponse({"error": "Only POST method allowed"}, status=405)


@login_required
@csrf_exempt
def complete_stop_go_penalty(request):
    """API endpoint to mark an active Stop & Go penalty as served/completed."""
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            queue_id = data.get("queue_id")
            
            queue_entry = get_object_or_404(StopAndGoQueue, id=queue_id)
            
            # Can only complete active penalties
            if queue_entry.status != 'active':
                return JsonResponse({
                    "success": False, 
                    "error": "Can only complete active penalties"
                }, status=400)
            
            # Complete the penalty
            queue_entry.complete()
            
            # Activate next penalty in queue after a delay
            next_penalty = StopAndGoQueue.get_next_in_queue(queue_entry.round.id)
            if next_penalty:
                # TODO: Add 10-second delay mechanism here
                next_penalty.activate()
            
            return JsonResponse({
                "success": True,
                "message": "Penalty completed successfully",
                "next_penalty_activated": next_penalty.id if next_penalty else None
            })
            
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)}, status=400)
    
    return JsonResponse({"error": "Only POST method allowed"}, status=405)