from django.urls import path, include
from . import views

from . import dash_app
from . import dash_app_portfolio

urlpatterns = [
	path('', views.home, name="home"),
	path('about.html', views.about, name="about"),
	path("portfolio/<str:pk>/", views.portfolio, name="portfolio"),
]