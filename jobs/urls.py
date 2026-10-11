from django.urls import path

from .views import JobDetailView, JobListView, JobOfferSubmitView

urlpatterns = [
    path("", JobListView.as_view(), name="job-list"),
    path("<int:pk>/", JobDetailView.as_view(), name="job-detail"),
    path("<int:pk>/offers/", JobOfferSubmitView.as_view(), name="job-offer-submit"),
]
