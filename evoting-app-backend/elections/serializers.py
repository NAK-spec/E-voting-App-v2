from datetime import date

from django.conf import settings
from django.db.models import Q
from rest_framework import serializers

from elections.models import Candidate, Poll, PollPosition, Position, VotingStation


# =========================
# VOTING STATION
# =========================
class VotingStationSerializer(serializers.ModelSerializer):
    registered_voter_count = serializers.ReadOnlyField()
    load_percentage = serializers.ReadOnlyField()

    class Meta:
        model = VotingStation
        fields = [
            "id", "name", "location", "region", "capacity", "supervisor",
            "contact", "opening_time", "closing_time", "is_active",
            "registered_voter_count", "load_percentage", "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class VotingStationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = VotingStation
        fields = [
            "name", "location", "region", "capacity", "supervisor",
            "contact", "opening_time", "closing_time",
        ]

    def validate_capacity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Capacity must be greater than zero.")
        return value


# =========================
# CANDIDATE
# =========================
class CandidateSerializer(serializers.ModelSerializer):
    age = serializers.ReadOnlyField()
    education_display = serializers.CharField(
        source="get_education_display", read_only=True
    )

    class Meta:
        model = Candidate
        fields = [
            "id", "full_name", "national_id", "date_of_birth", "age",
            "gender", "education", "education_display", "party", "manifesto",
            "address", "phone", "email", "has_criminal_record",
            "years_experience", "is_active", "is_approved", "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class CandidateCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Candidate
        fields = [
            "full_name", "national_id", "date_of_birth", "gender",
            "education", "party", "manifesto", "address", "phone",
            "email", "has_criminal_record", "years_experience",
        ]

    def validate_national_id(self, value):
        qs = Candidate.objects.filter(national_id=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                "A candidate with this National ID already exists."
            )
        return value

    def validate_date_of_birth(self, value):
        today = date.today()
        age = today.year - value.year - (
            (today.month, today.day) < (value.month, value.day)
        )

        if age < settings.MIN_CANDIDATE_AGE:
            raise serializers.ValidationError(
                f"Candidate must be at least {settings.MIN_CANDIDATE_AGE} years old."
            )
        if age > settings.MAX_CANDIDATE_AGE:
            raise serializers.ValidationError(
                f"Candidate must not be older than {settings.MAX_CANDIDATE_AGE}."
            )
        return value

    def validate_has_criminal_record(self, value):
        if value:
            raise serializers.ValidationError(
                "Candidates with criminal records are not eligible."
            )
        return value


class CandidateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Candidate
        fields = [
            "full_name", "national_id", "party", "manifesto",
            "phone", "email", "address", "years_experience",
        ]

    def validate_national_id(self, value):
        qs = Candidate.objects.filter(national_id=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                "A candidate with this National ID already exists."
            )
        return value


# =========================
# POSITION
# =========================
class PositionSerializer(serializers.ModelSerializer):
    level_display = serializers.CharField(
        source="get_level_display", read_only=True
    )

    class Meta:
        model = Position
        fields = [
            "id", "title", "description", "level", "level_display",
            "max_winners", "min_candidate_age", "is_active", "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class PositionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Position
        fields = [
            "title", "description", "level",
            "max_winners", "min_candidate_age"
        ]

    def validate_max_winners(self, value):
        if value < 1:
            raise serializers.ValidationError("Must be at least 1.")
        return value


# =========================
# POLL POSITION
# =========================
class PollPositionSerializer(serializers.ModelSerializer):
    position = PositionSerializer(read_only=True)
    candidates = CandidateSerializer(many=True, read_only=True)

    class Meta:
        model = PollPosition
        fields = ["id", "position", "candidates"]


# =========================
# POLL
# =========================
class PollSerializer(serializers.ModelSerializer):
    poll_positions = PollPositionSerializer(many=True, read_only=True)
    total_votes_cast = serializers.ReadOnlyField()
    station_ids = serializers.PrimaryKeyRelatedField(
        source="stations", many=True, read_only=True
    )

    class Meta:
        model = Poll
        fields = [
            "id", "title", "description", "election_type", "start_date",
            "end_date", "status", "station_ids", "poll_positions",
            "total_votes_cast", "created_at",
        ]
        read_only_fields = ["id", "status", "created_at"]


class PollCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=300)
    description = serializers.CharField(required=False, default="")
    election_type = serializers.ChoiceField(choices=Poll.ElectionType.choices)
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    position_ids = serializers.ListField(
        child=serializers.IntegerField(), min_length=1
    )
    station_ids = serializers.ListField(
        child=serializers.IntegerField(), min_length=1
    )

    def validate(self, data):
        # Date validation
        if data["end_date"] < data["start_date"]:
            raise serializers.ValidationError(
                {"end_date": "End date must be after start date."}
            )

        # Prevent overlapping polls
        overlapping = Poll.objects.filter(
            Q(start_date__lte=data["end_date"]) &
            Q(end_date__gte=data["start_date"])
        )
        if overlapping.exists():
            raise serializers.ValidationError(
                "Another poll overlaps with these dates."
            )

        # Validate positions
        valid_positions = Position.objects.filter(
            pk__in=data["position_ids"]
        ).values_list("pk", flat=True)

        invalid_positions = set(data["position_ids"]) - set(valid_positions)
        if invalid_positions:
            raise serializers.ValidationError(
                {"position_ids": f"Invalid positions: {invalid_positions}"}
            )

        # Validate stations
        valid_stations = VotingStation.objects.filter(
            pk__in=data["station_ids"], is_active=True
        ).values_list("pk", flat=True)

        invalid_stations = set(data["station_ids"]) - set(valid_stations)
        if invalid_stations:
            raise serializers.ValidationError(
                {"station_ids": f"Invalid or inactive stations: {invalid_stations}"}
            )

        return data


class PollUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Poll
        fields = [
            "title", "description", "election_type",
            "start_date", "end_date"
        ]


# =========================
# ASSIGN CANDIDATES
# =========================
class AssignCandidatesSerializer(serializers.Serializer):
    poll_position_id = serializers.IntegerField()
    candidate_ids = serializers.ListField(
        child=serializers.IntegerField()
    )

    def validate_candidate_ids(self, value):
        existing = set(
            Candidate.objects.filter(pk__in=value, is_active=True)
            .values_list("pk", flat=True)
        )
        invalid = set(value) - existing
        if invalid:
            raise serializers.ValidationError(
                f"Invalid or ineligible candidates: {invalid}"
            )
        return value

    def validate(self, data):
        poll_position = PollPosition.objects.get(
            pk=data["poll_position_id"]
        )

        max_winners = poll_position.position.max_winners

        if len(data["candidate_ids"]) > max_winners:
            raise serializers.ValidationError(
                f"Cannot assign more than {max_winners} candidates."
            )

        return data
