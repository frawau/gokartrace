# race/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from django_apscheduler.jobstores import DjangoJobStore
import asyncio as aio
import threading

def racing_start():
    # Don't create a new event loop here
    scheduler = AsyncIOScheduler()
    scheduler.add_jobstore(DjangoJobStore(), "default")

    # Import task
    from race.tasks import RaceTasks
    scheduler.add_job(RaceTasks.race_events, "interval", minutes=1, id="race-event-task")

    # Start in a background thread
    thread = threading.Thread(target=start_scheduler, args=(scheduler,))
    thread.daemon = True
    thread.start()

def start_scheduler(scheduler):
    # Create loop here in the thread
    loop = aio.new_event_loop()
    aio.set_event_loop(loop)
    scheduler.start()
    loop.run_forever()
