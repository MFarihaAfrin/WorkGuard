from django.urls import path
from . import views

urlpatterns = [
    path('faq/', views.faq_view, name='faq'),
    path('contact/', views.contact_view, name='contact'),

    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('logout/', views.logout_view, name='logout'),
    path('employees/', views.employees_view, name='employees'),
    path('employees/add/', views.add_employee_view, name='add_employee'),
    path('employees/<int:pk>/', views.view_employee_view, name='view_employee'),
    path('employees/<int:pk>/edit/', views.edit_employee_view, name='edit_employee'),
    path('employees/<int:pk>/delete/', views.delete_employee_view, name='delete_employee'),
    path('departments/', views.departments_view, name='departments'),
    path('departments/add/', views.add_department_view, name='add_department'),
    path('departments/<int:pk>/', views.view_department_view, name='view_department'),
    path('departments/<int:pk>/edit/', views.edit_department_view, name='edit_department'),
    path('departments/<int:pk>/delete/', views.delete_department_view, name='delete_department'),
    path('profile/', views.my_profile_view, name='my_profile'),
    path('notifications/', views.notifications_view, name='notifications'),
    path('reports/', views.reports_view, name='reports'),
    path('employees/<int:pk>/reset-password/', views.reset_password_view, name='reset_password'),
]