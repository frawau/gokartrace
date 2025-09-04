# Simplified Stop & Go Queue Management API
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json
import datetime as dt
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import threading

from .models import Round, RoundPenalty, StopAndGoQueue, ChampionshipPenalty


def send_next_penalty_to_station(next_penalty, delay_seconds=10):
    """Send next penalty to station after specified delay"""

    async def send_penalty_after_delay():
        import asyncio

        await asyncio.sleep(delay_seconds)
        try:
            channel_layer = get_channel_layer()
            message = {
                "type": "penalty_required",
                "team": next_penalty.round_penalty.offender.team.number,
                "duration": next_penalty.round_penalty.value,
                "penalty_id": next_penalty.round_penalty.id,
                "queue_id": next_penalty.id,
                "timestamp": dt.datetime.now().isoformat(),
            }
            await channel_layer.group_send(
                "stopandgo",
                {"type": "penalty_notification", "message": message},
            )
            print(
                f"Sent next penalty for team {next_penalty.round_penalty.offender.team.number} to station"
            )
        except Exception as e:
            print(f"Error sending next penalty to station: {e}")

    # Start background thread with new event loop
    def run_delayed_send():
        import asyncio

        try:
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(send_penalty_after_delay())
        except Exception as e:
            print(f"Error in delayed send thread: {e}")
        finally:
            loop.close()

    thread = threading.Thread(target=run_delayed_send, daemon=True)
    thread.start()


@login_required
@csrf_exempt
def get_stop_go_queue_status(request, round_id):
    """Get current queue status - next penalty + queue count."""
    try:
        round_obj = get_object_or_404(Round, id=round_id)

        # Get next penalty (oldest timestamp)
        next_penalty = StopAndGoQueue.get_next_penalty(round_id)
        next_penalty_data = None

        if next_penalty:
            next_penalty_data = {
                "queue_id": next_penalty.id,
                "penalty_id": next_penalty.round_penalty.id,
                "team_number": next_penalty.round_penalty.offender.team.number,
                "team_name": next_penalty.round_penalty.offender.team.team.name,
                "penalty_name": next_penalty.round_penalty.penalty.penalty.name,
                "value": next_penalty.round_penalty.value,
                "timestamp": next_penalty.timestamp.isoformat(),
            }

        # Get queue count
        queue_count = StopAndGoQueue.get_queue_count(round_id)

        return JsonResponse(
            {
                "success": True,
                "next_penalty": next_penalty_data,
                "queue_count": queue_count,
            }
        )

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

            # Delete the queue entry (cancelling it)
            round_id = queue_entry.round.id
            queue_entry.delete()

            # Get the next penalty in queue
            next_penalty = StopAndGoQueue.get_next_penalty(round_id)

            # Send next penalty to station after 10 second delay
            if next_penalty:
                send_next_penalty_to_station(next_penalty)

            return JsonResponse(
                {
                    "success": True,
                    "message": "Penalty cancelled successfully",
                    "next_penalty_id": next_penalty.id if next_penalty else None,
                }
            )

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

            # Check if we should create an "ignoring s&g" penalty
            create_ignoring_penalty = False
            ignoring_penalty = None

            try:
                # Look for "ignoring s&g" penalty in the championship
                championship = queue_entry.round.championship
                ignoring_penalty = ChampionshipPenalty.objects.filter(
                    championship=championship, penalty__name__icontains="ignoring"
                ).first()

                if ignoring_penalty:
                    create_ignoring_penalty = True
            except:
                pass  # If no ignoring penalty exists, just delay without creating one

            # Delay the current penalty (update timestamp to move to end of queue)
            queue_entry.timestamp = dt.datetime.now()
            queue_entry.save()

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
                    served=None,
                )
                ignoring_penalty_id = ignoring_round_penalty.id

            # Get the next penalty in queue
            next_penalty = StopAndGoQueue.get_next_penalty(queue_entry.round.id)

            # Send next penalty to station after 10 second delay
            if next_penalty:
                send_next_penalty_to_station(next_penalty)

            return JsonResponse(
                {
                    "success": True,
                    "message": "Penalty delayed and moved to end of queue",
                    "delayed_penalty_id": queue_entry.id,
                    "next_penalty_id": next_penalty.id if next_penalty else None,
                    "ignoring_penalty_created": ignoring_penalty_id is not None,
                    "ignoring_penalty_id": ignoring_penalty_id,
                }
            )

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

            # Mark the associated round penalty as served
            queue_entry.round_penalty.served = dt.datetime.now()
            queue_entry.round_penalty.save()

            # Delete the queue entry (completing it)
            round_id = queue_entry.round.id
            queue_entry.delete()

            # Get the next penalty in queue
            next_penalty = StopAndGoQueue.get_next_penalty(round_id)

            # Send next penalty to station after 10 second delay (for manual completion)
            if next_penalty:
                send_next_penalty_to_station(next_penalty)

            return JsonResponse(
                {
                    "success": True,
                    "message": "Penalty completed successfully",
                    "next_penalty_id": next_penalty.id if next_penalty else None,
                }
            )

        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)}, status=400)

    return JsonResponse({"error": "Only POST method allowed"}, status=405)
