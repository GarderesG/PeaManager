from django.urls import path, include
from . import views

from . import dash_app
from . import dash_app_portfolio
from . import dash_instrument_comparison

urlpatterns = [
	path('', views.home, name="home"),
	path('about.html', views.about, name="about"),
	path("portfolio/<str:pk>/", views.portfolio, name="portfolio"),
    path("instrument-comparison", views.instrument_comparison, name="instrument_comparison"),
]