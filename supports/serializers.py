from rest_framework import serializers


from .models import *
# from user.serializers import UserSerializer


class FAQListSerializer(serializers.ModelSerializer):

    class Meta:
        model = FAQ
        fields = [
            'id', 'question',
            'answer', #, 'order',
            'created_at', 'updated_at'
        ]
        read_only_fields = fields


class FAQSerializer(serializers.ModelSerializer):
    class Meta:
        model = FAQ
        fields = ['id', 'question', 'answer']
        read_only_fields = ['id']

    def validate_question(self, value):
        value = value.strip()
        if len(value) < 10:
            raise serializers.ValidationError("Question must be at least 10 characters")
        return value


class AboutUsSerializer(serializers.ModelSerializer):

    class Meta:
        model = AboutUs
        fields = ['content', 'updated_at']
        read_only_fields = ['updated_at']


class TermsAndConditionsSerializer(serializers.ModelSerializer):

    class Meta:
        model = TermsAndConditions
        fields = [
            'content',
            'updated_at'
        ]
        read_only_fields = ['updated_at']


class PrivacyPolicySerializer(serializers.ModelSerializer):

    class Meta:
        model = PrivacyPolicy
        fields = [
            'content',
            'updated_at'
        ]
        read_only_fields = ['updated_at']
        

class FeedbackCreateSerializer(serializers.ModelSerializer):
    """Used by authenticated users to submit feedback"""

    class Meta:
        model = Feedback
        fields = ['id', 'subject', 'email', 'message', 'attachment', 'created_at']
        read_only_fields = ['id', 'created_at']



class FeedbackAdminSerializer(serializers.ModelSerializer):
    """Used by admin for full CRUD"""

    class Meta:
        model = Feedback
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']
        
        