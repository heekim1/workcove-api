from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.views import APIView


class APIRootView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(
            {
                "register": reverse("register", request=request),
                "login": reverse("login", request=request),
                "verify": reverse("verify", request=request),
                "refresh": reverse("token_refresh", request=request),
                "jobs": reverse("job-list", request=request),
                "admin": reverse("admin:index", request=request),
            }
        )
