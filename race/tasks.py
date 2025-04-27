# race/tasks.py

import asyncio as aio
import datetime as dt
from django.db.models import Q


class RaceTasks:

    _lock = aio.Semaphore(1)

    @classmethod
    async def race_events(cls):
        # Try to acquire the semaphore
        if not cls._lock.locked():
            async with cls._lock:
                from .models import Round, ChangeLane

                end_date = dt.date.today()
                start_date = end_date - dt.timedelta(days=1)
                cround = (
                    await Round.objects.filter(
                        Q(start__date__range=[start_date, end_date])
                        & Q(ended__isnull=True)
                    )
                    .first()
                    .aawait_sync()
                )
                if not cround.ready:
                    # nothing to do
                    return

                if not cround.started:
                    # Nothing to do
                    return

                elapsed = await cround.async_time_elapsed()
                if elapsed < cround.pitlane_open_after:
                    # Do we wait for it?
                    if (elapsed - cround.pitlane_open_after) <= dt.timedelta(
                        seconds=65
                    ):
                        # Let's wwait
                        await aio.sleep(
                            (elapsed - cround.pitlane_open_after).total_seconds()
                        )
                        change_lanes = await ChangeLane.objects.filter(
                            round=cround, open=False
                        ).aawait_sync()
                        for alane in change_lanes:
                            alane.open = True
                            await alane.asave()
                elif cround.duration - elapsed - cround.pitlane_close_before < dt.timedelta(
                    seconds=65
                ):
                    await aio.sleep(
                        (
                            cround.duration - elapsed - cround.pitlane_close_before
                        ).total_seconds()
                    )
                    change_lanes = await ChangeLane.objects.filter(
                        round=cround, open=True, driver__isnull=True
                    ).aawait_sync()
                    for alane in change_lanes:
                        alane.open = False
                        await alane.asave()

        else:
            # bail out
            return

def run_race_events():
    """Wrapper function to run the async race_events task."""
    aio.run(RaceTasks.race_events())
