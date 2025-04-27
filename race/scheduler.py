# race/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from django_apscheduler.jobstores import DjangoJobStore


def racing_start():
    scheduler = AsyncIOScheduler()
    scheduler.add_jobstore(DjangoJobStore(), "default")

    # Schedule your task
    from race.tasks import RaceTasks  # import here to avoid circular imports

    scheduler.add_job(RaceTasks.race_events, "interval", minutes=1, id="race-event-task")

    scheduler.start()
