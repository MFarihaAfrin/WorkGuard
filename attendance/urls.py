from django.urls import path
from . import views

urlpatterns = [
    path('mark/', views.mark_attendance_view, name='mark_attendance'),
    path('history/', views.attendance_history_view, name='attendance_history'),
    path('team/', views.team_attendance_view, name='team_attendance'),
    path('all/', views.all_attendance_view, name='all_attendance'),
    path('<int:pk>/edit/', views.edit_attendance_view, name='edit_attendance'),
    path('employee/<int:pk>/history/', views.employee_history_view, name='employee_attendance_history'),
    path('report/', views.attendance_report_view, name='attendance_report'),
    path('report/pdf/', views.attendance_report_pdf_view, name='attendance_report_pdf'),
]