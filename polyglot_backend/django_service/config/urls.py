from django.contrib import admin
from django.http import JsonResponse
from django.urls import path


def health(_request):
    return JsonResponse({"success": True, "message": "healthcheck", "data": {"service": "django", "status": "healthy"}})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("health", health),
]