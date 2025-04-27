# race/scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from django_apscheduler.jobstores import DjangoJobStore
from django.db import connection

def racing_start():
    # Close any existing connections first
    connection.close()

    # Create scheduler
    scheduler = BackgroundScheduler()

    # Import the standalone function
    from race.tasks import run_race_events

    # Add job using the function reference (must be at module level)
    scheduler.add_job(run_race_events, "interval", minutes=1, id="race-event-task", replace_existing=True)

    # Only add the jobstore after defining jobs to avoid initialization DB access
    scheduler.add_jobstore(DjangoJobStore(), "default")

    # Start the scheduler
    scheduler.start()
