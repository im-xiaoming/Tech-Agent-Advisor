from django.urls import path

from accounts.views import AccountLoginView, logout_view, register_view


urlpatterns = [
    path("login/", AccountLoginView.as_view(), name="login"),
    path("register/", register_view, name="register"),
    path("logout/", logout_view, name="logout"),
]
