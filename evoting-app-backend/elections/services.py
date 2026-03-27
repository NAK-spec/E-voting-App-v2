from datetime import date

from django.db import transaction
from django.db.models import Q
from django.core.exceptions import ObjectDoesNotExist

from audit.services import AuditService
from elections.models import Candidate, Poll, PollPosition, Position, VotingStation


# =========================
# CANDIDATE SERVICE
# =========================
class CandidateService:
    def __init__(self):
        self._audit = AuditService()

    def create(self, validated_data, created_by):
        candidate = Candidate.objects.create(created_by=created_by, **validated_data)
        self._audit.log(
            "CREATE_CANDIDATE",
            created_by.username,
            f"Created candidate: {candidate.full_name} (ID: {candidate.id})",
        )
        return candidate

    def update(self, candidate, validated_data, updated_by):
        for key, value in validated_data.items():
            setattr(candidate, key, value)
        candidate.save()

        self._audit.log(
            "UPDATE_CANDIDATE",
            updated_by.username,
            f"Updated candidate: {candidate.full_name} (ID: {candidate.id})",
        )
        return candidate

    def deactivate(self, candidate_id, deleted_by):
        try:
            candidate = Candidate.objects.get(pk=candidate_id)
        except Candidate.DoesNotExist:
            raise ValueError("Candidate not found.")

        candidate.is_active = False
        candidate.save(update_fields=["is_active"])

        self._audit.log(
            "DELETE_CANDIDATE",
            deleted_by.username,
            f"Deactivated candidate: {candidate.full_name} (ID: {candidate.id})",
        )
        return candidate

    def search(self, query_params):
        qs = Candidate.objects.all()

        if name := query_params.get("name"):
            qs = qs.filter(full_name__icontains=name)

        if party := query_params.get("party"):
            qs = qs.filter(party__icontains=party)

        if education := query_params.get("education"):
            qs = qs.filter(education=education)

        # Age filtering (DB-safe)
        today = date.today()

        if min_age := query_params.get("min_age"):
            cutoff = date(today.year - int(min_age), today.month, today.day)
            qs = qs.filter(date_of_birth__lte=cutoff)

        if max_age := query_params.get("max_age"):
            cutoff = date(today.year - int(max_age), today.month, today.day)
            qs = qs.filter(date_of_birth__gte=cutoff)

        return qs


# =========================
# VOTING STATION SERVICE
# =========================
class VotingStationService:
    def __init__(self):
        self._audit = AuditService()

    def create(self, validated_data, created_by):
        station = VotingStation.objects.create(created_by=created_by, **validated_data)
        self._audit.log("CREATE_STATION", created_by.username, f"Created station: {station.name}")
        return station

    def update(self, station, validated_data, updated_by):
        for key, value in validated_data.items():
            setattr(station, key, value)
        station.save()

        self._audit.log("UPDATE_STATION", updated_by.username, f"Updated station: {station.name}")
        return station

    def deactivate(self, station_id, deleted_by):
        try:
            station = VotingStation.objects.get(pk=station_id)
        except VotingStation.DoesNotExist:
            raise ValueError("Voting station not found.")

        station.is_active = False
        station.save(update_fields=["is_active"])

        self._audit.log("DELETE_STATION", deleted_by.username, f"Deactivated station: {station.name}")
        return station


# =========================
# POSITION SERVICE
# =========================
class PositionService:
    def __init__(self):
        self._audit = AuditService()

    def create(self, validated_data, created_by):
        position = Position.objects.create(created_by=created_by, **validated_data)
        self._audit.log("CREATE_POSITION", created_by.username, f"Created position: {position.title}")
        return position

    def update(self, position, validated_data, updated_by):
        for key, value in validated_data.items():
            setattr(position, key, value)
        position.save()

        self._audit.log("UPDATE_POSITION", updated_by.username, f"Updated position: {position.title}")
        return position

    def deactivate(self, position_id, deleted_by):
        try:
            position = Position.objects.get(pk=position_id)
        except Position.DoesNotExist:
            raise ValueError("Position not found.")

        position.is_active = False
        position.save(update_fields=["is_active"])

        self._audit.log("DELETE_POSITION", deleted_by.username, f"Deactivated position: {position.title}")
        return position


# =========================
# POLL SERVICE
# =========================
class PollService:
    def __init__(self):
        self._audit = AuditService()

    @transaction.atomic
    def create(self, validated_data, created_by):
        poll = Poll.objects.create(
            title=validated_data["title"],
            description=validated_data.get("description", ""),
            election_type=validated_data["election_type"],
            start_date=validated_data["start_date"],
            end_date=validated_data["end_date"],
            status=Poll.Status.DRAFT,
            created_by=created_by,
        )

        poll.stations.set(
            VotingStation.objects.filter(pk__in=validated_data["station_ids"])
        )

        PollPosition.objects.bulk_create([
            PollPosition(poll=poll, position_id=pos_id)
            for pos_id in validated_data["position_ids"]
        ])

        self._audit.log("CREATE_POLL", created_by.username, f"Created poll: {poll.title}")
        return poll

    def update(self, poll, validated_data, updated_by):
        if poll.status == Poll.Status.OPEN:
            raise ValueError("Cannot update an open poll.")

        for key, value in validated_data.items():
            setattr(poll, key, value)

        poll.save()

        self._audit.log("UPDATE_POLL", updated_by.username, f"Updated poll: {poll.title}")
        return poll

    @transaction.atomic
    def delete(self, poll_id, deleted_by):
        try:
            poll = Poll.objects.get(pk=poll_id)
        except Poll.DoesNotExist:
            raise ValueError("Poll not found.")

        if poll.status == Poll.Status.OPEN:
            raise ValueError("Cannot delete an open poll.")

        title = poll.title
        poll.delete()

        self._audit.log("DELETE_POLL", deleted_by.username, f"Deleted poll: {title}")

    def toggle_status(self, poll_id, action, toggled_by):
        poll = Poll.objects.prefetch_related("poll_positions__candidates").get(pk=poll_id)

        old_status = poll.status

        if action == "open":
            if old_status not in (Poll.Status.DRAFT, Poll.Status.CLOSED):
                raise ValueError("Invalid state transition.")

            if old_status == Poll.Status.DRAFT:
                has_candidates = any(pp.candidates.exists() for pp in poll.poll_positions.all())
                if not has_candidates:
                    raise ValueError("Cannot open - no candidates assigned.")

            poll.status = Poll.Status.OPEN
            log_action = "OPEN_POLL" if old_status == Poll.Status.DRAFT else "REOPEN_POLL"

        elif action == "close":
            if old_status != Poll.Status.OPEN:
                raise ValueError("Only open polls can be closed.")

            poll.status = Poll.Status.CLOSED
            log_action = "CLOSE_POLL"

        else:
            raise ValueError("Invalid action.")

        poll.save(update_fields=["status"])

        self._audit.log(
            log_action,
            toggled_by.username,
            f"{log_action.replace('_', ' ').title()}: {poll.title}",
        )

        return poll

    @transaction.atomic
    def assign_candidates(self, poll_position_id, candidate_ids, assigned_by):
        poll_position = PollPosition.objects.select_related("poll", "position").get(
            pk=poll_position_id
        )

        if poll_position.poll.status == Poll.Status.OPEN:
            raise ValueError("Cannot modify candidates of an open poll.")

        candidates = Candidate.objects.filter(
            pk__in=candidate_ids,
            is_active=True,
            is_approved=True,
        )

        if candidates.count() != len(candidate_ids):
            raise ValueError("Some candidates are invalid or not eligible.")

        max_winners = poll_position.position.max_winners
        if candidates.count() > max_winners:
            raise ValueError(f"Maximum {max_winners} candidates allowed.")

        poll_position.candidates.set(candidates)

        self._audit.log(
            "ASSIGN_CANDIDATES",
            assigned_by.username,
            f"Assigned {candidates.count()} candidates to {poll_position.position.title}",
        )

        return poll_position
