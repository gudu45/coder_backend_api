# proposal/urls.py

from django.urls import path
from . import views

urlpatterns = [
    path('rfps/<int:rfp_id>/send/', views.send_rfp_to_vendors, name='send_rfp'),
    path('rfps/<int:rfp_id>/compare/', views.compare_proposals, name='compare_proposals'),
    path('webhooks/resend-inbound/', views.resend_inbound_webhook, name='resend_inbound'),
]