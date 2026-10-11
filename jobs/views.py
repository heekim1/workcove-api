from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from workers.models import WorkerProfile

from .models import Job, JobOffer
from .serializers import JobDetailSerializer, JobOfferSerializer, JobSerializer


class IsWorker(BasePermission):
    message = "Only a worker can view jobs."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == User.Role.WORKER
        )


class OpenJobQueryset:
    def get_queryset(self):
        return Job.objects.filter(status=Job.Status.OPEN).select_related("skill", "manager")


class JobListView(OpenJobQueryset, ListAPIView):
    # Login is off until the SMS code can be delivered.
    # permission_classes = [IsAuthenticated, IsWorker]
    serializer_class = JobSerializer


class JobDetailView(OpenJobQueryset, RetrieveAPIView):
    # Login is off until the SMS code can be delivered.
    # permission_classes = [IsAuthenticated, IsWorker]
    serializer_class = JobDetailSerializer


class JobOfferSubmitView(APIView):
    # Login is off until the SMS code can be delivered.
    # permission_classes = [IsAuthenticated, IsWorker]

    def post(self, request, pk):
        if not getattr(request.user, "is_authenticated", False):
            raise ValidationError({"detail": "Log in as a worker before submitting an offer."})
        job = get_object_or_404(Job.objects.filter(status=Job.Status.OPEN), pk=pk)
        try:
            worker = request.user.worker_profile
        except WorkerProfile.DoesNotExist:
            raise ValidationError({"detail": "Create a worker profile before submitting an offer."})
        if JobOffer.objects.filter(job=job, worker=worker).exists():
            raise ValidationError({"detail": "You already submitted an offer for this job."})
        offer = JobOffer.objects.create(job=job, worker=worker, channel=JobOffer.Channel.APP)
        return Response(JobOfferSerializer(offer).data, status=201)
