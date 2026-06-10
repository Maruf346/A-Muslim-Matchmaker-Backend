from django.db import models
import uuid
from django_ckeditor_5.fields import CKEditor5Field
from django.core.exceptions import ValidationError
from django.conf import settings


class FAQ(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    question = models.CharField(max_length=500)
    answer = models.CharField(max_length=500)
    # order = models.PositiveIntegerField(
    #     default=0,
    #     help_text='Order in which FAQs appear (lower numbers first)'
    # )
    # is_active = models.BooleanField(
    #     default=True,
    #     help_text='Whether this FAQ is visible to users'
    # )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'FAQ'
        verbose_name_plural = 'FAQs'
        ordering = ['-created_at']
        
    def __str__(self):
        return self.question
    

class AboutUs(models.Model):
    content = CKEditor5Field('Content', config_name='extends')
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'About Us'
        verbose_name_plural = 'About Us'
        
    def save(self, *args, **kwargs):
        # Singleton
        if not self.pk and AboutUs.objects.exists():
            raise ValidationError('Only one About Us instance allowed.')
        return super().save(*args, **kwargs)
    
    def __str__(self):
        return 'About Us Content'
    
    
class TermsAndConditions(models.Model):
    content = CKEditor5Field('Content', config_name='extends')
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Terms and Conditions'
        verbose_name_plural = 'Terms and Conditions'
        
    def save(self, *args, **kwargs):
        # Singleton
        if not self.pk and TermsAndConditions.objects.exists():
            raise ValidationError('Only one Terms & Conditions instance allowed.')
        return super().save(*args, **kwargs)
    
    def __str__(self):
        return 'Terms and Conditions'

    
class PrivacyPolicy(models.Model):
    content = CKEditor5Field('Content', config_name='extends')
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Privacy Policy'
        verbose_name_plural = 'Privacy Policy'
    
    def save(self, *args, **kwargs):
        # Singleton
        if not self.pk and PrivacyPolicy.objects.exists():
            raise ValidationError("Only one Privacy Policy instance allowed.")
        return super().save(*args, **kwargs)
    
    def __str__(self):
        return 'Privacy Policy'
    
    
class Feedback(models.Model):
    """
    Submitted by clients or artisans via the app's feedback form.
    User is automatically linked from request.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='feedbacks'
    )
    subject = models.CharField(max_length=400)
    email = models.EmailField()
    message = models.TextField()
    attachment = models.FileField(upload_to='feedback_attachments/', null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Feedback from {self.email}: {self.subject}"

    class Meta:
        verbose_name = 'Feedback'
        verbose_name_plural = 'Feedbacks'
        ordering = ['-created_at']

