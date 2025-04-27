# race/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from django_apscheduler.jobstores import DjangoJobStore
import asyncio as aio

def racing_start():

    loop = aio.new_event_loop()
    aio.set_event_loop(loop)
    scheduler = AsyncIOScheduler()
    scheduler.add_jobstore(DjangoJobStore(), "default")

    # Schedule your task
    from race.tasks import RaceTasks  # import here to avoid circular imports

    scheduler.add_job(RaceTasks.race_events, "interval", minutes=1, id="race-event-task")
    # Start in a background thread
    import threading
    thread = threading.Thread(target=start_loop, args=(loop, scheduler))
    thread.daemon = True
    thread.start()

def start_loop(loop, scheduler):
    asyncio.set_event_loop(loop)
    scheduler.start()
    loop.run_forever()
