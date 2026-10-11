from rest_framework import serializers

from .models import Job, JobOffer


class JobSerializer(serializers.ModelSerializer):
    skill = serializers.CharField(source="skill.name", read_only=True)
    business_name = serializers.CharField(source="manager.business_name", read_only=True)

    class Meta:
        model = Job
        fields = (
            "id",
            "work_date",
            "start_time",
            "end_time",
            "city",
            "state",
            "zip_code",
            "hourly_rate",
            "headcount",
            "status",
            "skill",
            "business_name",
        )


class JobDetailSerializer(JobSerializer):
    my_offer = serializers.SerializerMethodField()

    class Meta(JobSerializer.Meta):
        fields = JobSerializer.Meta.fields + ("my_offer",)

    def get_my_offer(self, job):
        user = self.context["request"].user
        if not getattr(user, "is_authenticated", False):
            return None
        offer = job.offers.filter(worker__user_id=user.pk).first()
        if offer is None:
            return None
        return JobOfferSerializer(offer).data


class JobOfferSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobOffer
        fields = ("id", "reply_code", "status", "channel")
