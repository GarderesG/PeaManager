from django.urls import path, include
from quotes import views, dash_app, dash_app_portfolio, dash_instrument_comparison

urlpatterns = [
	path('', views.home, name="home"),
	path('about.html', views.about, name="about"),
	path("portfolio/<str:pk>/", views.portfolio, name="portfolio"),
    path("instrument-comparison", views.instrument_comparison, name="instrument_comparison"),
]