import datetime as dt
import time
import random
import threading
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from race.models import (
    Session,
    Round,
    team_member,
    ChampionshipPenalty,
    RoundPenalty,
)


class Command(BaseCommand):
    help = "Simulate a realistic race with driver changes and penalties."

    def add_arguments(self, parser):
        parser.add_argument(
            "--average-lap-time",
            type=float,
            default=90.0,
            help="Average lap time in seconds (default: 90)",
        )
        parser.add_argument(
            "--real-time-speed",
            type=float,
            default=60.0,
            help="Simulation speed multiplier - how many seconds of race time per real second (default: 60)",
        )
        parser.add_argument(
            "--penalty-probability",
            type=float,
            default=0.15,
            help="Probability of penalty per team per hour (default: 0.15)",
        )
        parser.add_argument(
            "--verbose", action="store_true", help="Enable verbose logging"
        )

    def handle(self, *args, **options):
        self.verbose = options["verbose"]
        self.average_lap_time = options["average_lap_time"]
        self.real_time_speed = options["real_time_speed"]
        self.penalty_probability = options["penalty_probability"]

        # Find current round
        start_date = dt.date.today() - dt.timedelta(days=1)
        end_date = start_date + dt.timedelta(days=60)
        cround = Round.objects.filter(
            Q(start__date__range=[start_date, end_date]) & Q(ended__isnull=True)
        ).first()

        if not cround:
            raise CommandError("Could not find an active round to simulate")

        self.round = cround
        self.log(f"Starting simulation for round: {cround.name}")
        self.log(f"Race duration: {cround.duration}")
        self.log(f"Average lap time: {self.average_lap_time}s")
        self.log(f"Real-time speed: {self.real_time_speed}x")

        try:
            self.simulate_full_race()
        except KeyboardInterrupt:
            self.log("Simulation interrupted by user")
        except Exception as e:
            self.log(f"Simulation error: {e}")
            raise

    def log(self, message):
        """Log with timestamp"""
        timestamp = dt.datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")
        if self.verbose:
            self.stdout.write(f"[{timestamp}] {message}")

    def simulate_full_race(self):
        """Run complete race simulation"""

        # Phase 1: Register first drivers (like firstregister command)
        self.log("Phase 1: Registering first drivers...")
        self.register_first_drivers()

        # Phase 2: Pre-race check
        self.log("Phase 2: Running pre-race check...")
        errors = self.round.pre_race_check()
        if errors:
            raise CommandError(f"Pre-race check failed: {errors}")
        self.log("Pre-race check passed ✓")

        # Phase 3: Start race
        self.log("Phase 3: Starting race...")
        self.round.start_race()
        self.log("Race started ✓")

        # Phase 4: Simulate race duration with pit stops and penalties
        self.log("Phase 4: Simulating race...")
        self.simulate_race_events()

        # Phase 5: End race
        self.log("Phase 5: Ending race...")
        penalty_count = self.round.end_race()
        self.log(f"Race ended ✓ ({penalty_count} post-race penalties applied)")

    def register_first_drivers(self):
        """Register one driver per team (like firstregister command)"""
        teams = self.round.round_team_set.all().order_by("team__number")
        now = dt.datetime.now()

        for team in teams:
            driver = team.team_member_set.filter(driver=True).order_by("?").first()
            if driver:
                session = Session.objects.create(
                    round=self.round, driver=driver, register=now
                )
                self.log(
                    f"  Registered {driver.member.nickname} for team {team.number}"
                )

    def simulate_race_events(self):
        """Simulate the race duration with realistic timing"""
        race_duration_seconds = self.round.duration.total_seconds()
        pitlane_open_after_seconds = self.round.pitlane_open_after.total_seconds()
        pitlane_close_before_seconds = self.round.pitlane_close_before.total_seconds()

        # Calculate when pit lane opens and closes
        pitlane_open_at = pitlane_open_after_seconds
        pitlane_close_at = race_duration_seconds - pitlane_close_before_seconds

        self.log(f"Race will run for {race_duration_seconds/60:.1f} minutes")
        self.log(f"Pit lane opens at {pitlane_open_at/60:.1f} minutes")
        self.log(f"Pit lane closes at {pitlane_close_at/60:.1f} minutes")

        # Get all teams and their driver change requirements
        teams = list(self.round.round_team_set.all())
        team_stats = self.initialize_team_stats(teams)

        # Time tracking
        elapsed_time = 0
        last_penalty_check = 0

        # Stop & Go penalty tracking
        active_stop_go_penalty = None
        penalty_serve_time = 0
        penalty_timeout_time = 0

        # Event loop
        while elapsed_time < race_duration_seconds:
            # Sleep for simulation speed
            time.sleep(1.0 / self.real_time_speed)
            elapsed_time += 1

            # Check if pit lane is open
            pit_lane_open = pitlane_open_at <= elapsed_time <= pitlane_close_at

            if pit_lane_open:
                # Simulate driver changes
                self.simulate_driver_changes(elapsed_time, team_stats)

                # Check for penalties every 5 minutes of race time (only if no active Stop & Go)
                if (
                    elapsed_time - last_penalty_check >= 300
                    and active_stop_go_penalty is None  # 5 minutes
                ):
                    penalty = self.simulate_penalties(elapsed_time)
                    if penalty and penalty.penalty.sanction in [
                        "S",
                        "D",
                    ]:  # Stop & Go penalties
                        active_stop_go_penalty = penalty
                        # Calculate realistic serve time with randomness
                        serve_delay = self.calculate_penalty_serve_time()
                        penalty_serve_time = elapsed_time + serve_delay + penalty.value
                        penalty_timeout_time = elapsed_time + (
                            3.5 * self.average_lap_time
                        )  # Auto-ignore after ~3.5 laps

                        laps_to_serve = serve_delay / self.average_lap_time
                        self.log(
                            f"🚨 Active Stop & Go penalty - team will serve after ~{laps_to_serve:.1f} laps ({serve_delay:.0f}s)"
                        )
                    last_penalty_check = elapsed_time

                # Check if it's time to serve the active Stop & Go penalty OR if it timed out
                if active_stop_go_penalty:
                    if elapsed_time >= penalty_serve_time:
                        # Team served the penalty in time
                        success = self.serve_stop_go_penalty(active_stop_go_penalty)
                        if success:
                            self.log(
                                f"✅ Stop & Go penalty served for team {active_stop_go_penalty.offender.number}"
                            )
                            active_stop_go_penalty = None
                            penalty_serve_time = 0
                            penalty_timeout_time = 0
                    elif elapsed_time >= penalty_timeout_time:
                        # Team ignored penalty - issue "ignoring stop & go" penalty
                        ignore_penalty = self.issue_ignoring_penalty(
                            active_stop_go_penalty.offender
                        )
                        if ignore_penalty:
                            self.log(
                                f"⚠️ Team {active_stop_go_penalty.offender.number} ignored Stop & Go - issued '{ignore_penalty.penalty.penalty.name}' penalty"
                            )
                        else:
                            self.log(
                                f"⚠️ Team {active_stop_go_penalty.offender.number} ignored Stop & Go - no 'ignoring s&g' penalty configured"
                            )

                        # Clear the ignored Stop & Go penalty
                        active_stop_go_penalty = None
                        penalty_serve_time = 0
                        penalty_timeout_time = 0

            # Log progress every 10 minutes of race time
            if elapsed_time % 600 == 0:  # Every 10 minutes
                self.log(
                    f"Race progress: {elapsed_time/60:.1f}/{race_duration_seconds/60:.1f} minutes"
                )

        self.log_final_stats(team_stats)

    def initialize_team_stats(self, teams):
        """Initialize tracking stats for each team"""
        team_stats = {}

        for team in teams:
            drivers = list(team.team_member_set.filter(driver=True))

            # Calculate realistic driver change pattern
            required_changes = self.round.required_changes

            # Add variation: 70% meet requirement, 20% do more, 10% do less
            variation = random.random()
            if variation < 0.7:
                target_changes = required_changes
            elif variation < 0.9:
                target_changes = required_changes + random.randint(1, 3)
            else:
                target_changes = max(1, required_changes - random.randint(1, 2))

            team_stats[team.id] = {
                "team": team,
                "drivers": drivers,
                "target_changes": target_changes,
                "completed_changes": 0,
                "next_queue_time": self.calculate_next_queue_time(0),
                "has_queued_driver": False,
                "change_ready_time": 0,
                "top_queue_reached_time": 0,  # When team reached top queue positions
            }

            self.log(
                f"Team {team.number} ({team.team.team.name}): targeting {target_changes} changes"
            )

        return team_stats

    def calculate_next_queue_time(self, current_time):
        """Calculate realistic next driver queue time"""
        # Vary stint length: 15-45 minutes with some randomness
        base_stint = random.uniform(15 * 60, 45 * 60)  # 15-45 minutes in seconds

        # Add lap time variation (complete current lap)
        lap_variation = random.uniform(0.8, 1.2) * self.average_lap_time

        return current_time + base_stint + lap_variation

    def calculate_penalty_serve_time(self):
        """Calculate realistic time for team to serve Stop & Go penalty"""
        # Realistic distribution of penalty serving behavior:
        # 30% serve after 1 lap
        # 40% serve after 2 laps
        # 20% serve after 3 laps
        # 8% serve after 3+ laps (will trigger ignoring penalty)
        # 2% serve after 4+ laps (will trigger ignoring penalty)

        rand = random.random()
        if rand < 0.30:  # 30% - serve after ~1 lap
            return random.uniform(0.8, 1.2) * self.average_lap_time
        elif rand < 0.70:  # 40% - serve after ~2 laps
            return random.uniform(1.8, 2.2) * self.average_lap_time
        elif rand < 0.90:  # 20% - serve after ~3 laps
            return random.uniform(2.8, 3.2) * self.average_lap_time
        elif rand < 0.98:  # 8% - serve after 3.5+ laps (too late)
            return random.uniform(3.5, 4.0) * self.average_lap_time
        else:  # 2% - serve after 4+ laps (way too late)
            return random.uniform(4.0, 5.0) * self.average_lap_time

    def simulate_driver_changes(self, elapsed_time, team_stats):
        """Simulate realistic driver changes using proper driver_queue -> driver_change flow"""

        # Phase 1: Handle driver_queue registrations (drivers coming to pit lane)
        for team_id, stats in team_stats.items():
            team = stats["team"]

            # Check if it's time for this team to queue a driver
            if (
                elapsed_time >= stats["next_queue_time"]
                and stats["completed_changes"] < stats["target_changes"]
                and not stats.get("has_queued_driver", False)
            ):

                success = self.perform_driver_queue(team, elapsed_time)
                if success:
                    stats["has_queued_driver"] = True
                    # Set time for actual driver change (about 2 laps later)
                    stats["change_ready_time"] = elapsed_time + (
                        2 * self.average_lap_time
                    )
                    self.log(
                        f"Team {team.number}: driver queued, change ready in {2 * self.average_lap_time:.0f}s"
                    )

        # Phase 2: Check for teams in top queue positions and track timing
        for team_id, stats in team_stats.items():
            team = stats["team"]

            if stats.get("has_queued_driver", False):
                # Check if team just reached top queue positions
                if stats[
                    "top_queue_reached_time"
                ] == 0 and self.team_in_top_queue_positions(team):
                    stats["top_queue_reached_time"] = elapsed_time
                    self.log(
                        f"Team {team.number}: reached top {self.round.change_lanes} queue positions"
                    )

                # Check if driver change is ready and team is in position
                if elapsed_time >= stats.get(
                    "change_ready_time", 0
                ) and self.team_ready_for_change(team):

                    success = self.perform_driver_change(team, elapsed_time)
                    if success:
                        # Calculate how long they took from reaching top positions
                        if stats["top_queue_reached_time"] > 0:
                            queue_delay = elapsed_time - stats["top_queue_reached_time"]
                            max_allowed_delay = 3 * self.average_lap_time

                            if queue_delay > max_allowed_delay:
                                # Issue "driver change too long" penalty
                                slow_change_penalty = (
                                    self.issue_driver_change_too_long_penalty(
                                        team, queue_delay
                                    )
                                )
                                if slow_change_penalty:
                                    self.log(
                                        f"⏰ Team {team.number} took {queue_delay:.0f}s for driver change - issued '{slow_change_penalty.penalty.penalty.name}' penalty"
                                    )

                        stats["completed_changes"] += 1
                        stats["has_queued_driver"] = False
                        stats["top_queue_reached_time"] = 0
                        stats["next_queue_time"] = self.calculate_next_queue_time(
                            elapsed_time
                        )

                        self.log(
                            f"Team {team.number}: driver change completed #{stats['completed_changes']}"
                        )

    def perform_driver_queue(self, team, elapsed_time):
        """Register a driver for the queue (driver_queue equivalent)"""
        try:
            # Find drivers who are NOT currently on track (all sessions complete)
            available_drivers = []
            for driver in team.team_member_set.filter(driver=True):
                # Check if driver has any active session (registered, started, not ended)
                active_session = Session.objects.filter(
                    round=self.round,
                    driver=driver,
                    register__isnull=False,
                    start__isnull=False,
                    end__isnull=True,
                ).exists()

                if not active_session:
                    available_drivers.append(driver)

            if not available_drivers:
                return False

            # Pick a random available driver
            next_driver = random.choice(available_drivers)

            # Register them for the queue (equivalent to scanning driver_queue)
            result = self.round.driver_register(next_driver)

            if result["status"] == "ok":
                self.log(f"  {next_driver.member.nickname} added to queue")
                return True
            else:
                self.log(
                    f"  Failed to queue {next_driver.member.nickname}: {result['message']}"
                )

        except Exception as e:
            self.log(f"Driver queue failed: {e}")

        return False

    def team_in_top_queue_positions(self, team):
        """Check if team has someone in the top queue positions"""
        pending_sessions = Session.objects.filter(
            round=self.round,
            register__isnull=False,
            start__isnull=True,
            end__isnull=True,
        ).order_by("register")[
            : self.round.change_lanes
        ]  # Top N positions based on pit lanes

        return any(session.driver.team == team for session in pending_sessions)

    def team_ready_for_change(self, team):
        """Check if team is ready for driver change"""
        # Team must have someone in top queue positions
        if not self.team_in_top_queue_positions(team):
            return False

        # Team must have exactly one driver currently on track
        current_drivers = Session.objects.filter(
            round=self.round,
            driver__team=team,
            register__isnull=False,
            start__isnull=False,
            end__isnull=True,
        )

        return current_drivers.count() == 1

    def perform_driver_change(self, team, elapsed_time):
        """Perform actual driver change (driver_change equivalent)"""
        try:
            # Find the current driver on track for this team
            current_session = Session.objects.filter(
                round=self.round,
                driver__team=team,
                register__isnull=False,
                start__isnull=False,
                end__isnull=True,
            ).first()

            if not current_session:
                return False

            # Simulate pit lane delay (30-60 seconds)
            pit_delay = random.uniform(30, 60) / self.real_time_speed
            time.sleep(pit_delay)

            # End current driver's session (this should start the queued driver)
            result = self.round.driver_endsession(current_session.driver)

            if result["status"] == "ok":
                return True
            else:
                self.log(f"  Driver change failed: {result['message']}")

        except Exception as e:
            self.log(f"Driver change failed: {e}")

        return False

    def simulate_penalties(self, elapsed_time):
        """Randomly issue penalties (only championship-registered ones)"""
        # Get all available penalties for this championship
        all_penalties = ChampionshipPenalty.objects.filter(
            championship=self.round.championship
        )

        if not all_penalties:
            return None

        teams = list(self.round.round_team_set.all())

        # Check each team for potential penalty
        for team in teams:
            # Random penalty chance based on probability per hour
            hours_elapsed = elapsed_time / 3600
            penalty_chance = self.penalty_probability * (hours_elapsed / len(teams))

            if random.random() < penalty_chance:
                # Issue a random penalty from available ones
                penalty = random.choice(all_penalties)

                # Find potential victim (different team, for regular Stop & Go)
                victim = None
                if penalty.sanction == "S":  # Regular Stop & Go needs victim
                    other_teams = [t for t in teams if t != team]
                    if other_teams:
                        victim = random.choice(other_teams)

                # Create penalty with appropriate served timestamp
                served_time = None
                if penalty.sanction in [
                    "L",
                    "P",
                ]:  # Laps and Post Race Laps are auto-served
                    served_time = dt.datetime.now()

                round_penalty = RoundPenalty.objects.create(
                    round=self.round,
                    offender=team,
                    victim=victim,
                    penalty=penalty,
                    value=penalty.value,
                    imposed=dt.datetime.now(),
                    served=served_time,
                )

                # Log penalty type appropriately
                if penalty.sanction == "S":
                    penalty_type = "Stop & Go"
                elif penalty.sanction == "D":
                    penalty_type = "Self Stop & Go"
                elif penalty.sanction == "L":
                    penalty_type = "Laps"
                elif penalty.sanction == "P":
                    penalty_type = "Post Race Laps"
                else:
                    penalty_type = penalty.penalty.name

                victim_str = f" (victim: team {victim.number})" if victim else ""

                if penalty.sanction in ["S", "D"]:
                    self.log(
                        f"🚨 {penalty_type} penalty issued to team {team.number}{victim_str} - needs serving"
                    )
                    return round_penalty  # Only return Stop & Go penalties for tracking
                else:
                    self.log(
                        f"📋 {penalty_type} penalty issued to team {team.number}{victim_str} - auto-handled"
                    )
                    return None  # Other penalties don't need tracking

        return None

    def serve_stop_go_penalty(self, round_penalty):
        """Simulate serving a Stop & Go penalty (equivalent to clicking 'Served' button)"""
        try:
            # Update penalty served timestamp (equivalent to /api/update-penalty-served/)
            round_penalty.served = dt.datetime.now()
            round_penalty.save()

            penalty_type = (
                "Self Stop & Go"
                if round_penalty.penalty.sanction == "D"
                else "Stop & Go"
            )
            self.log(
                f"  {penalty_type} penalty served: {round_penalty.value}s for team {round_penalty.offender.number}"
            )
            return True

        except Exception as e:
            self.log(f"Failed to serve Stop & Go penalty: {e}")
            return False

    def issue_ignoring_penalty(self, offender_team):
        """Issue 'ignoring stop & go' penalty for teams that don't serve in time"""
        try:
            # Look for "ignoring s&g" or similar penalty in championship
            ignore_penalties = ChampionshipPenalty.objects.filter(
                championship=self.round.championship,
                penalty__name__icontains="ignoring",
            ).filter(penalty__name__icontains="stop")

            if not ignore_penalties:
                # Also try looking for generic "ignore" penalties or lap penalties
                ignore_penalties = ChampionshipPenalty.objects.filter(
                    championship=self.round.championship,
                    penalty__name__icontains="ignore",
                )

            if not ignore_penalties:
                return None

            # Use the first matching penalty
            ignore_penalty = ignore_penalties.first()

            # Create the ignoring penalty
            round_penalty = RoundPenalty.objects.create(
                round=self.round,
                offender=offender_team,
                victim=None,  # Ignoring penalties don't have victims
                penalty=ignore_penalty,
                value=ignore_penalty.value,
                imposed=dt.datetime.now(),
                served=dt.datetime.now()
                if ignore_penalty.sanction in ["L", "P"]
                else None,  # Lap penalties are served immediately
            )

            return round_penalty

        except Exception as e:
            self.log(f"Failed to issue ignoring penalty: {e}")
            return None

    def issue_driver_change_too_long_penalty(self, offender_team, delay_seconds):
        """Issue 'driver change too long' penalty for slow pit stops"""
        try:
            # Look for "driver change too long" or similar penalty in championship
            slow_change_penalties = ChampionshipPenalty.objects.filter(
                championship=self.round.championship,
                penalty__name__icontains="driver change",
            ).filter(penalty__name__icontains="long")

            if not slow_change_penalties:
                # Also try looking for "too long" penalties
                slow_change_penalties = ChampionshipPenalty.objects.filter(
                    championship=self.round.championship,
                    penalty__name__icontains="too long",
                )

            if not slow_change_penalties:
                return None

            # Use the first matching penalty
            slow_penalty = slow_change_penalties.first()

            # Create the slow driver change penalty
            round_penalty = RoundPenalty.objects.create(
                round=self.round,
                offender=offender_team,
                victim=None,  # Driver change penalties don't have victims
                penalty=slow_penalty,
                value=slow_penalty.value,
                imposed=dt.datetime.now(),
                served=dt.datetime.now()
                if slow_penalty.sanction in ["L", "P"]
                else None,  # Auto-serve if it's laps
            )

            return round_penalty

        except Exception as e:
            self.log(f"Failed to issue driver change too long penalty: {e}")
            return None

    def log_final_stats(self, team_stats):
        """Log final simulation statistics"""
        self.log("\n=== SIMULATION COMPLETE ===")
        self.log("Final team statistics:")

        for team_id, stats in team_stats.items():
            team = stats["team"]
            actual_sessions = Session.objects.filter(
                round=self.round, driver__team=team, end__isnull=False
            ).count()

            self.log(f"Team {team.number} ({team.team.team.name}):")
            self.log(f"  Target changes: {stats['target_changes']}")
            self.log(f"  Completed sessions: {actual_sessions}")
            self.log(f"  Required changes: {self.round.required_changes}")

        # Log penalties
        penalties = RoundPenalty.objects.filter(round=self.round)
        served_penalties = penalties.filter(served__isnull=False)
        self.log(f"\nPenalties issued during race: {penalties.count()}")
        self.log(f"Stop & Go penalties served: {served_penalties.count()}")

        for penalty in penalties:
            served_status = "✅ SERVED" if penalty.served else "⏳ PENDING"
            penalty_type = penalty.penalty.penalty.name
            victim_info = (
                f" (victim: team {penalty.victim.number})" if penalty.victim else ""
            )
            self.log(
                f"  {penalty_type} - Team {penalty.offender.number}{victim_info} - {served_status}"
            )
