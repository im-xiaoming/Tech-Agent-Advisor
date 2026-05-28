from django.shortcuts import render
from django.urls import reverse


def landing_view(request):
    return render(
        request,
        "landing/landing.html",
        {
            "chat_url": reverse("chat-view"),
        },
    )
