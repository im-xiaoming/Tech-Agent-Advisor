from django.urls import path

from manager.views import config_manager, log_detail, log_flag, log_list, product_data_view


urlpatterns = [
    path("config/", config_manager, name="manager-config"),
    path("data/", product_data_view, name="manager-product-data"),
    path("logs/", log_list, name="manager-log-list"),
    path("logs/<int:log_id>/", log_detail, name="manager-log-detail"),
    path("logs/<int:log_id>/flag/", log_flag, name="manager-log-flag"),
]
