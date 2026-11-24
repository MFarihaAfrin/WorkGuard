from django.urls import path
from . import views

urlpatterns = [
    path('submit/', views.submit_claim_view, name='submit_claim'),
    path('my-claims/', views.my_claims_view, name='my_claims'),
    path('team/', views.team_claims_view, name='team_claims'),
    path('<int:pk>/decide/', views.decide_claim_view, name='decide_claim'),
    path('budgets/', views.budget_overview_view, name='budget_overview'),
    path('final/', views.final_approval_view, name='final_approval'),
    path('<int:pk>/final-decide/', views.final_decide_view, name='final_decide'),
    path('<int:pk>/delete/', views.delete_claim_view, name='delete_claim'),
    path('<int:pk>/mark-paid/', views.mark_paid_view, name='mark_paid'),
    path('claim/<int:pk>/pdf/', views.claim_pdf_view, name='claim_pdf'),
    path('submit/confirm/<int:pk>/', views.confirm_claim_view, name='confirm_claim'),
]