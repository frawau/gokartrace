# race/scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from django_apscheduler.jobstores import DjangoJobStore
import threading

def racing_start():
    scheduler = BackgroundScheduler()
    scheduler.add_jobstore(DjangoJobStore(), "default")

    # Import task
    from race.tasks import RaceTasks

    # Add a job that calls the async function using a regular function wrapper
    def run_race_events():
        import asyncio
        asyncio.run(RaceTasks.race_events())

    scheduler.add_job(run_race_events, "interval", minutes=1, id="race-event-task")

    # Start the scheduler directly
    scheduler.start()
