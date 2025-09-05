# race/tasks.py

import asyncio as aio
import datetime as dt
from django.db.models import Q
from asgiref.sync import sync_to_async
from channels.layers import get_channel_layer
from .signals import race_end_requested


class RaceTasks:

    _lock = aio.Semaphore(1)
    _penalty_queue_event = aio.Event()
    _penalty_queue_data = []
    _penalty_queue_lock = aio.Lock()

    @classmethod
    async def race_events(cls):
        # Try to acquire the semaphore
        if not cls._lock.locked():
            async with cls._lock:
                from .models import Round, ChangeLane

                end_date = dt.date.today()
                start_date = end_date - dt.timedelta(days=1)
                cround = await Round.objects.filter(
                    Q(start__date__range=[start_date, end_date]) & Q(ended__isnull=True)
                ).afirst()
                if not cround:
                    return
                if not cround.ready:
                    # nothing to do
                    return

                if not cround.started:
                    # Nothing to do
                    return

                if cround.ended:
                    # Nothing to do
                    return

                elapsed = await cround.async_time_elapsed()
                if elapsed < cround.pitlane_open_after:
                    # Do we wait for it?
                    if (cround.pitlane_open_after) - elapsed <= dt.timedelta(
                        seconds=65
                    ):
                        dowait = (cround.pitlane_open_after - elapsed).total_seconds()
                        while int(dowait) > 0:
                            await aio.sleep(dowait)
                            elapsed = await cround.async_time_elapsed()
                            dowait = (
                                cround.pitlane_open_after - elapsed
                            ).total_seconds()
                        change_lanes = await sync_to_async(list)(
                            ChangeLane.objects.filter(round=cround, open=False)
                        )
                        for alane in change_lanes:
                            alane.open = True
                            await alane.asave()
                elif cround.duration - elapsed < dt.timedelta(seconds=65):
                    # Check for end before check for close pit lane. Would not be reached otherwise
                    dowait = (cround.duration - elapsed).total_seconds()
                    print(f"\n\n\nClosing in {dowait} seconds!\n\n\n")
                    while int(dowait) > 0:
                        await aio.sleep(dowait)
                        elapsed = await cround.async_time_elapsed()
                        dowait = (cround.duration - elapsed).total_seconds()
                        if not cround.ended:
                            await race_end_requested.asend(
                                sender=cls, round_id=cround.id
                            )
                elif (
                    cround.duration - elapsed - cround.pitlane_close_before
                    < dt.timedelta(seconds=65)
                ):
                    dowait = (
                        cround.duration - elapsed - cround.pitlane_close_before
                    ).total_seconds()
                    while int(dowait) > 0:
                        await aio.sleep(dowait)
                        elapsed = await cround.async_time_elapsed()
                        dowait = (
                            cround.duration - elapsed - cround.pitlane_close_before
                        ).total_seconds()
                    change_lanes = await sync_to_async(list)(
                        ChangeLane.objects.filter(
                            round=cround, open=True, driver__isnull=True
                        )
                    )
                    for alane in change_lanes:
                        alane.open = False
                        await alane.asave()

        else:
            # bail out
            return

    @classmethod
    async def queue_penalty_notification(cls, penalty_data, delay_seconds=10):
        """Queue a penalty notification to be sent after delay"""
        async with cls._penalty_queue_lock:
            cls._penalty_queue_data.append(
                {
                    "penalty_data": penalty_data,
                    "delay": delay_seconds,
                    "queue_time": dt.datetime.now(),
                    "send_time": dt.datetime.now()
                    + dt.timedelta(seconds=delay_seconds),
                }
            )
            cls._penalty_queue_event.set()  # Signal that there's work to do

        print(
            f"Queued penalty notification for team {penalty_data['team']} with {delay_seconds}s delay"
        )

    @classmethod
    async def penalty_queue_processor(cls):
        """Process penalty queue notifications"""
        channel_layer = get_channel_layer()

        while True:
            try:
                # Wait for notifications to be queued
                await cls._penalty_queue_event.wait()

                # Process all pending notifications
                async with cls._penalty_queue_lock:
                    now = dt.datetime.now()
                    ready_to_send = []
                    remaining = []

                    for item in cls._penalty_queue_data:
                        if now >= item["send_time"]:
                            ready_to_send.append(item)
                        else:
                            remaining.append(item)

                    cls._penalty_queue_data = remaining

                    # Clear event if no more items
                    if not cls._penalty_queue_data:
                        cls._penalty_queue_event.clear()

                # Send ready notifications
                for item in ready_to_send:
                    try:
                        penalty_data = item["penalty_data"]
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

                    except Exception as e:
                        print(f"Error sending penalty notification: {e}")

                # Sleep briefly before checking again
                await aio.sleep(1)

            except Exception as e:
                print(f"Error in penalty queue processor: {e}")
                await aio.sleep(5)


def run_race_events():
    """Wrapper function to run the async race_events task."""

    async def run_both():
        # Start both the race events and penalty queue processor
        await aio.gather(RaceTasks.race_events(), RaceTasks.penalty_queue_processor())

    aio.run(run_both())
