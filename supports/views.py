from django.shortcuts import render
from rest_framework import viewsets, views
from rest_framework import generics
from rest_framework.permissions import IsAdminUser, IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.generics import UpdateAPIView, RetrieveAPIView, ListAPIView
from rest_framework import status
from drf_spectacular.utils import extend_schema, extend_schema_view
from .serializers import *
from .models import *
import logging
from django.utils.decorators import method_decorator
from notifications.services import NotificationTemplates
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.shortcuts import get_object_or_404

from users.permissions import IsAdminUser



logger = logging.getLogger(__name__)


@extend_schema(tags=["Supports - Shared"])
@extend_schema_view(
    list=extend_schema(
        summary="List FAQs",
        description="Retrieve a list of frequently asked questions. "
                    "Supports searching by question/answer and ordering by creation or update date."
    ),
    retrieve=extend_schema(
        summary="Get a specific FAQ",
        description="Retrieve the details of a specific FAQ entry by its ID. "
                    "Authenticated users can view."
    )
)
class ListFAQViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = FAQ.objects.all()
    serializer_class = FAQListSerializer
    ordering_fields = ['created_at', 'updated_at']
    search_fields = ['question', 'answer']
    ordering = ['-created_at']
    
    
@extend_schema_view(
    list=extend_schema(
        tags=['Supports - Admin'],
        summary="List FAQs (Admin)",
        description="Admin view to list all FAQs."
    ),
    retrieve=extend_schema(
        tags=['Supports - Admin'],
        summary="Retrieve FAQ",
        description="Retrieve details of a specific FAQ."
    ),
    create=extend_schema(
        tags=['Supports - Admin'],
        summary="Create FAQ",
        description="Admin can create a new FAQ."
    ),
    update=extend_schema(
        tags=['Supports - Admin'],
        summary="Update FAQ",
        description="Admin can fully update an existing FAQ."
    ),
    partial_update=extend_schema(
        tags=['Supports - Admin'],
        summary="Partially update FAQ",
        description="Admin can partially update an existing FAQ."
    ),
    destroy=extend_schema(
        tags=['Supports - Admin'],
        summary="Delete FAQ",
        description="Admin can delete an FAQ."
    ),
)
class FAQViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminUser]
    queryset = FAQ.objects.all()
    serializer_class = FAQSerializer
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    

@extend_schema(
    tags=['Supports - Shared'],
    summary="Get About Us content",
    description="Retrieve the About Us information for public or authenticated users."
)
class AboutUsPublicView(RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AboutUsSerializer
    
    def get_object(self):
        return AboutUs.objects.first()
    

@extend_schema(
    tags=['Supports - Admin'],
    summary="Update About Us",
    description="Admin can update the About Us content. Only PATCH requests are allowed."
)
class AboutUsAdminUpdateView(UpdateAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = AboutUsSerializer
    http_method_names = ['patch']
    
    def get_object(self):
        return AboutUs.objects.first()
    
    def perform_update(self, serializer):
        serializer.save()
        logger.info('About Us updated')
        
        
@extend_schema(
    tags=['Supports - Shared'],
    summary="Get Terms and Conditions",
    description="Retrieve the Terms and Conditions content for public or authenticated users."
)
class TermsAndConditionsPublicView(RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TermsAndConditionsSerializer
    
    def get_object(self):
        return TermsAndConditions.objects.first()


@extend_schema(
    tags=['Supports - Admin'],
    summary="Update Terms and Conditions",
    description="Admin can update the Terms and Conditions content. Only PATCH requests are allowed."
)
class TermsAndConditionsAdminUpdateView(UpdateAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = TermsAndConditionsSerializer
    
    http_method_names = ['patch']
    
    def get_object(self):
        return TermsAndConditions.objects.first()
    
    def perform_update(self, serializer):
        serializer.save()
        logger.info('Terms and Conditions updated')


@extend_schema(
    tags=['Supports - Shared'],
    summary="Get Privacy Policy",
    description="Retrieve the Privacy Policy content for public or authenticated users."
)
class PrivacyPolicyPublicView(RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PrivacyPolicySerializer
    
    def get_object(self):
        return PrivacyPolicy.objects.first()
        
    
@extend_schema(
    tags=['Supports - Admin'],
    summary="Update Privacy Policy",
    description="Admin can update the Privacy Policy content. Only PATCH requests are allowed."
)
class PrivacyPolicyAdminUpdateView(UpdateAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = PrivacyPolicySerializer
    http_method_names = ['patch']
    
    def get_object(self):
        return PrivacyPolicy.objects.first()
    
    def perform_update(self, serializer):
        serializer.save()
        logger.info('Privacy Policy updated')
        

@extend_schema(
    tags=['Supports - Shared'],
    summary="Submit Feedback",
    description="Users (Male/Female/Wali) can submit feedback about the platform."
)
class FeedbackCreateView(generics.CreateAPIView):
    """Users (Male/Female/Wali) submit feedback"""
    serializer_class = FeedbackCreateSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


@extend_schema(
    tags=['Supports - Shared'],
    summary="List User Feedback",
    description="Users can view a list of their own feedback submissions."
)
class UserFeedbackListView(generics.ListAPIView):
    """User can see their own feedbacks"""
    serializer_class = FeedbackCreateSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Feedback.objects.filter(user=self.request.user)
    
    
@extend_schema(
    tags=['Supports - Admin'],
    summary="Admin Feedback Management",
    description="Admin can view, update, or delete all feedback submissions from users."
)
class FeedbackAdminViewSet(viewsets.ModelViewSet):
    """Admin can CRUD all feedbacks"""
    queryset = Feedback.objects.all()
    serializer_class = FeedbackAdminSerializer
    permission_classes = [IsAdminUser]
    
    
@extend_schema(
    tags=['Supports - Shared'],
    summary="Get Privacy Header",
    description="Retrieve the Privacy Header content for public or authenticated users."
)
class PrivacyHeaderPublicView(RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = PrivacyHeaderPublicSerializer
    
    def get_object(self):
        return PrivacyHeader.objects.first()
    
    
@extend_schema(
    tags=['Supports - Admin'],
    summary="Update Privacy Header",
    description="Admin can update the Privacy Header content. Only PATCH requests are allowed."
)
class PrivacyHeaderAdminView(UpdateAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = PrivacyHeaderAdminSerializer
    http_method_names = ['patch']
    
    def get_object(self):
        return PrivacyHeader.objects.first()
    
    def perform_update(self, serializer):
        serializer.save()
        logger.info('Privacy Header updated')