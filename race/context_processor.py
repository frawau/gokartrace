# race/context_processors.py
import datetime as dt
from django.db.models import Q
from django.core.cache import cache
from yourapp.models import Round


def active_round_data(request):
    # Try to get from cache first
    change_lanes = cache.get("active_round_change_lanes")

    if change_lanes is None:
        # Value not in cache, fetch from database
        end_date = dt.date.today()
        start_date = end_date - dt.timedelta(days=1)
        cround = Round.objects.filter(
            Q(start__date__range=[start_date, end_date]) & Q(ended__isnull=True)
        ).first()

        change_lanes = cround.change_lanes if cround else 0

        # Cache the value for 1 hour (or however long you need)
        cache.set("active_round_change_lanes", change_lanes, 3 * 60 * 60)

        return {"active_round_change_lanes": change_lanes}
