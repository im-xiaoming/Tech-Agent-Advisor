from django.urls import path

from manager.views import config_manager


urlpatterns = [
    path("config/", config_manager, name="manager-config"),
]
