# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

from django.contrib import admin
from django.urls import path, include
from debug_toolbar.toolbar import debug_toolbar_urls
from home.routing import websocket_urlpatterns
from channels.routing import URLRouter
try:
    from rest_framework.authtoken.views import obtain_auth_token
except:
    pass

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("home.urls")),
    path('ws/', URLRouter(websocket_urlpatterns)),
    path("", include("theme_material_kit.urls")),
    path("login/jwt/", view=obtain_auth_token),
] + debug_toolbar_urls()


# Lazy-load on routing is needed
# During the first build, API is not yet generated
try:
    urlpatterns.append(path("", include("django_dyn_api.urls")))
    urlpatterns.append(path("login/jwt/", view=obtain_auth_token))
except:
    pass
