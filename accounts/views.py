from django.conf import settings
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import (
    LoginSerializer,
    RegisterSerializer,
    UserSerializer,
    VerifyLoginSerializer,
)
from .services import AuthError, issue_login_code, verify_login_code
from .sms import SMSDeliveryError


class LoginRateThrottle(AnonRateThrottle):
    rate = "10/min"


class PublicAPIView(GenericAPIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get_throttles(self):
        if settings.IS_TESTING:
            return []
        return super().get_throttles()


def _error(exc):
    return Response(
        {"detail": exc.detail, "code": exc.code, **exc.extra},
        status=exc.status_code,
    )


def _tokens(user):
    refresh = RefreshToken.for_user(user)
    refresh["role"] = user.role
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "user": UserSerializer(user).data,
    }


class RegisterView(PublicAPIView):
    serializer_class = RegisterSerializer

    def post(self, request):
        serializer = RegisterSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserSerializer(user).data, status=201)


class LoginView(PublicAPIView):
    serializer_class = LoginSerializer
    throttle_classes = [LoginRateThrottle]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            challenge = issue_login_code(
                serializer.validated_data["email"],
                serializer.validated_data["password"],
            )
        except AuthError as exc:
            return _error(exc)
        except SMSDeliveryError as exc:
            return Response(
                {"detail": exc.detail, "code": "sms_failed"},
                status=503,
            )
        return Response(
            {
                "challenge_id": str(challenge.id),
                "expires_in": challenge.TTL_MINUTES * 60,
                "phone": f"***{challenge.user.phone[-4:]}",
            }
        )


class VerifyLoginView(PublicAPIView):
    serializer_class = VerifyLoginSerializer

    def post(self, request):
        serializer = VerifyLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = verify_login_code(
                serializer.validated_data["challenge_id"],
                serializer.validated_data["code"],
            )
        except AuthError as exc:
            return _error(exc)
        return Response(_tokens(user))
