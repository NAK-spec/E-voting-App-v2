from django.shortcuts import get_object_or_404

from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdminOrReadOnlyVoter, IsAdminUser
from elections.models import Candidate, Poll, Position, VotingStation, PollPosition
from elections.serializers import (
    AssignCandidatesSerializer,
    CandidateCreateSerializer,
    CandidateSerializer,
    CandidateUpdateSerializer,
    PollCreateSerializer,
    PollSerializer,
    PollUpdateSerializer,
    PositionCreateSerializer,
    PositionSerializer,
    VotingStationCreateSerializer,
    VotingStationSerializer,
)
from elections.services import (
    CandidateService,
    PollService,
    PositionService,
    VotingStationService,
)


# =========================
# CANDIDATE
# =========================
class CandidateListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdminOrReadOnlyVoter]

    def get_queryset(self):
        service = CandidateService()
        return service.search(self.request.query_params)

    def get_serializer_class(self):
        return CandidateCreateSerializer if self.request.method == "POST" else CandidateSerializer

    def create(self, request, *args, **kwargs):
        serializer = CandidateCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        service = CandidateService()
        candidate = service.create(serializer.validated_data, request.user)

        return Response(CandidateSerializer(candidate).data, status=status.HTTP_201_CREATED)


class CandidateDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAdminOrReadOnlyVoter]
    queryset = Candidate.objects.all()

    def get_serializer_class(self):
        return CandidateUpdateSerializer if self.request.method in ("PUT", "PATCH") else CandidateSerializer

    def perform_update(self, serializer):
        service = CandidateService()
        service.update(self.get_object(), serializer.validated_data, self.request.user)


class CandidateDeactivateView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        service = CandidateService()
        try:
            service.deactivate(pk, request.user)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_404_NOT_FOUND)

        return Response({"detail": "Candidate deactivated."})


# =========================
# VOTING STATION
# =========================
class VotingStationListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdminOrReadOnlyVoter]
    queryset = VotingStation.objects.filter(is_active=True)

    def get_serializer_class(self):
        return VotingStationCreateSerializer if self.request.method == "POST" else VotingStationSerializer

    def create(self, request, *args, **kwargs):
        serializer = VotingStationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        service = VotingStationService()
        station = service.create(serializer.validated_data, request.user)

        return Response(VotingStationSerializer(station).data, status=status.HTTP_201_CREATED)


class VotingStationDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAdminOrReadOnlyVoter]
    queryset = VotingStation.objects.all()

    def get_serializer_class(self):
        return VotingStationCreateSerializer if self.request.method in ("PUT", "PATCH") else VotingStationSerializer

    def perform_update(self, serializer):
        service = VotingStationService()
        service.update(self.get_object(), serializer.validated_data, self.request.user)


class VotingStationDeactivateView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        service = VotingStationService()
        try:
            service.deactivate(pk, request.user)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_404_NOT_FOUND)

        return Response({"detail": "Station deactivated."})


# =========================
# POSITION
# =========================
class PositionListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdminOrReadOnlyVoter]
    queryset = Position.objects.filter(is_active=True)

    def get_serializer_class(self):
        return PositionCreateSerializer if self.request.method == "POST" else PositionSerializer

    def create(self, request, *args, **kwargs):
        serializer = PositionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        service = PositionService()
        position = service.create(serializer.validated_data, request.user)

        return Response(PositionSerializer(position).data, status=status.HTTP_201_CREATED)


class PositionDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAdminOrReadOnlyVoter]
    queryset = Position.objects.all()

    def get_serializer_class(self):
        return PositionCreateSerializer if self.request.method in ("PUT", "PATCH") else PositionSerializer

    def perform_update(self, serializer):
        service = PositionService()
        service.update(self.get_object(), serializer.validated_data, self.request.user)


class PositionDeactivateView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        service = PositionService()
        try:
            service.deactivate(pk, request.user)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_404_NOT_FOUND)

        return Response({"detail": "Position deactivated."})


# =========================
# POLL
# =========================
class PollListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdminOrReadOnlyVoter]
    queryset = Poll.objects.all()
    serializer_class = PollSerializer

    def create(self, request, *args, **kwargs):
        serializer = PollCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        service = PollService()
        poll = service.create(serializer.validated_data, request.user)

        return Response(PollSerializer(poll).data, status=status.HTTP_201_CREATED)


class PollDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAdminOrReadOnlyVoter]
    queryset = Poll.objects.prefetch_related(
        "poll_positions__position",
        "poll_positions__candidates",
        "stations",
    )
    serializer_class = PollSerializer


class PollUpdateView(APIView):
    permission_classes = [IsAdminUser]

    def patch(self, request, pk):
        poll = get_object_or_404(Poll, pk=pk)

        serializer = PollUpdateSerializer(poll, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        service = PollService()
        try:
            service.update(poll, serializer.validated_data, request.user)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(PollSerializer(poll).data)


class PollDeleteView(APIView):
    permission_classes = [IsAdminUser]

    def delete(self, request, pk):
        service = PollService()
        try:
            service.delete(pk, request.user)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(status=status.HTTP_204_NO_CONTENT)


class PollToggleStatusView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        action = request.data.get("action")

        if action not in ("open", "close"):
            return Response(
                {"detail": "Action must be 'open' or 'close'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        service = PollService()
        try:
            poll = service.toggle_status(pk, action, request.user)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(PollSerializer(poll).data)


# =========================
# ASSIGN CANDIDATES
# =========================
class AssignCandidatesView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        serializer = AssignCandidatesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        service = PollService()
        try:
            poll_position = service.assign_candidates(
                serializer.validated_data["poll_position_id"],
                serializer.validated_data["candidate_ids"],
                request.user,
            )
        except (ValueError, PollPosition.DoesNotExist):
            return Response({"detail": "Invalid poll position or candidates."},
                            status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "detail": f"Candidates assigned to {poll_position.position.title}.",
            "candidate_count": poll_position.candidates.count(),
        })
