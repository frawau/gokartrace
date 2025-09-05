# Simplified Stop & Go Queue Management API
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json
import datetime as dt
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import asyncio
import queue
import threading

from .models import Round, RoundPenalty, StopAndGoQueue, ChampionshipPenalty

# Global queue for penalty notifications
penalty_notification_queue = queue.Queue()

# Flag to track if notification task is running
notification_task_running = False


def start_penalty_notification_task():
    """Start the penalty notification background task if not already running"""
    global notification_task_running

    if notification_task_running:
        return

    def notification_worker():
        """Background worker that processes penalty notifications"""
        global notification_task_running
        notification_task_running = True

        async def process_notifications():
            channel_layer = get_channel_layer()

            while True:
                try:
                    # Check for new notifications (non-blocking)
                    try:
                        penalty_data, delay = penalty_notification_queue.get_nowait()

                        if delay > 0:
                            await asyncio.sleep(delay)

                        message = {
                            "type": "penalty_required",
                            "team": penalty_data["team"],
                            "duration": penalty_data["duration"],
                            "penalty_id": penalty_data["penalty_id"],
                            "queue_id": penalty_data["queue_id"],
                            "timestamp": dt.datetime.now().isoformat(),
                        }

                        await channel_layer.group_send(
                            "stopandgo",
                            {"type": "penalty_notification", "message": message},
                        )

                        print(
                            f"Sent penalty notification for team {penalty_data['team']}"
                        )

                    except queue.Empty:
                        # No notifications pending, wait a bit
                        await asyncio.sleep(1)

                except Exception as e:
                    print(f"Error in penalty notification worker: {e}")
                    await asyncio.sleep(5)  # Wait before retrying

        # Run the async process in this thread
        asyncio.run(process_notifications())

    # Start the worker thread
    thread = threading.Thread(target=notification_worker, daemon=True)
    thread.start()
    print("Started penalty notification background task")


def send_next_penalty_to_station(next_penalty, delay_seconds=10):
    """Queue a penalty notification to be sent after delay"""
    # Ensure the notification task is running
    start_penalty_notification_task()

    # Add to queue
    penalty_data = {
        "team": next_penalty.round_penalty.offender.team.number,
        "duration": next_penalty.round_penalty.value,
        "penalty_id": next_penalty.round_penalty.id,
        "queue_id": next_penalty.id,
    }

    penalty_notification_queue.put((penalty_data, delay_seconds))
    print(
        f"Queued penalty notification for team {penalty_data['team']} with {delay_seconds}s delay"
    )


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
