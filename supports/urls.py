from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import *


router = DefaultRouter()
router.register(r'faqs', ListFAQViewSet, basename='faq-list')
router.register(r'faq/manage', FAQViewSet, basename='faq-manage')
router.register(r'admin/feedbacks', FeedbackAdminViewSet, basename='admin-feedback')



urlpatterns = [
    path('', include(router.urls)),

    # About Us
    # path('about-us/', AboutUsPublicView.as_view(), name='about-us-public'),
    # path('admin/about-us/', AboutUsAdminUpdateView.as_view(), name='about-us-admin'),
    
    # Terms and Conditions
    path('terms/', TermsAndConditionsPublicView.as_view(), name='terms-public'),
    path('admin/terms/', TermsAndConditionsAdminUpdateView.as_view(), name='terms-admin'),
    
    # Privacy Policy
    path('privacy/', PrivacyPolicyPublicView.as_view(), name='privacy-public'),
    path('admin/privacy/', PrivacyPolicyAdminUpdateView.as_view(), name='privacy-admin'),
    
    # Feedback
    path('feedback/submit/', FeedbackCreateView.as_view(), name='submit-feedback'),
    path('feedback/my-feedbacks/', UserFeedbackListView.as_view(), name='my-feedbacks'),
]
