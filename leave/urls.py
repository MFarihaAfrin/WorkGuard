from django.urls import path
from . import views

urlpatterns = [
    path('apply/', views.apply_leave_view, name='apply_leave'),
    path('history/', views.leave_history_view, name='leave_history'),
    path('team/', views.team_leave_view, name='team_leave'),
    path('<int:pk>/decide/', views.decide_leave_view, name='decide_leave'),
    path('all/', views.all_leave_view, name='all_leave'),
]