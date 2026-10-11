from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import LoginView, RegisterView, VerifyLoginView

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("verify/", VerifyLoginView.as_view(), name="verify"),
    path("refresh/", TokenRefreshView.as_view(), name="token_refresh"),
]
