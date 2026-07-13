from pathlib import Path
import os
from datetime import timedelta
from dotenv import load_dotenv
load_dotenv(override=False)


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-&2=269gpy_6f*npn9wr)tdn973w+%uhtw^mt(m3g88s&)ehfgf')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', 'True') == 'True'

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')


# Application definition

INSTALLED_APPS = [
    'daphne',
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    
    # Third-party apps
    'rest_framework',
    'corsheaders',
    'drf_spectacular',
    'django_filters',
    'django_redis',
    'phonenumber_field',
    'django_ckeditor_5',
    'channels',
    'django_celery_beat',
    
    # Local apps
    'api',
    'notifications',
    'users',
    'questions',
    'supports',
    'matches',
    'wishlists',
    'chat',
    'matchmaking',
    'private_matches',
    'dashboard',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # 'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'users.middleware.LastActiveMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'




# ── Security Settings ────────────────────────────────────────────────────────
# These are activated automatically when DEBUG=False (i.e. in production).
# Nginx terminates HTTP on port 80; after adding SSL, set SECURE_SSL_REDIRECT=True.
if not DEBUG:
    # Nginx forwards the real client IP via X-Forwarded-For
    USE_X_FORWARDED_HOST         = True
    SECURE_PROXY_SSL_HEADER      = ("HTTP_X_FORWARDED_PROTO", "https")
    # Don't redirect HTTP→HTTPS yet (we're on HTTP until domain+SSL is set up)
    SECURE_SSL_REDIRECT          = False
    SESSION_COOKIE_SECURE        = False  # Set True after SSL is configured
    CSRF_COOKIE_SECURE           = False  # Set True after SSL is configured
    SECURE_BROWSER_XSS_FILTER    = True
    SECURE_CONTENT_TYPE_NOSNIFF  = True
    X_FRAME_OPTIONS              = "SAMEORIGIN"
    # Enable these ONLY after SSL is working and tested:
    # SECURE_HSTS_SECONDS          = 31536000
    # SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    # SECURE_HSTS_PRELOAD          = True

# ── CORS & CSRF Settings ─────────────────────────────────────────────────────
_cors_origins_env = os.getenv('CORS_ALLOWED_ORIGINS', '')
if _cors_origins_env:
    CORS_ALLOWED_ORIGINS = [o.strip() for o in _cors_origins_env.split(',') if o.strip()]
    CORS_ALLOW_ALL_ORIGINS = False
else:
    # Development fallback — allow all
    CORS_ALLOW_ALL_ORIGINS = True

CORS_ALLOW_CREDENTIALS = True

# CSRF trusted origins: built from ALLOWED_HOSTS + any extra origins
_csrf_trusted = set([
    "http://localhost",
    "http://localhost:80",
    "http://127.0.0.1",
    "https://*.devtunnels.ms",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://admin.amuslimmatchmaker.com",
    "https://api.amuslimmatchmaker.com",
    "https://tgcg8q7d-5173.inc1.devtunnels.ms",
])
# Add any extra origins from CORS_ALLOWED_ORIGINS to CSRF_TRUSTED_ORIGINS
if _cors_origins_env:
    for _origin in _cors_origins_env.split(','):
        _origin = _origin.strip()
        if _origin:
            _csrf_trusted.add(_origin)
CSRF_TRUSTED_ORIGINS = list(_csrf_trusted)


# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases


DB_ENGINE = os.getenv('DB_ENGINE', 'django.db.backends.sqlite3')

if DB_ENGINE == 'django.db.backends.sqlite3':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db_volume' / 'db.sqlite3',
            # Stored in the named Docker volume → survives image rebuilds
        }
    }
else:
    # Production (PostgreSQL on AWS RDS) — just flip env vars, no code change needed
    DATABASES = {
        'default': {
            'ENGINE': DB_ENGINE,
            'NAME': os.getenv('DB_NAME'),
            'USER': os.getenv('DB_USER'),
            'PASSWORD': os.getenv('DB_PASSWORD'),
            'HOST': os.getenv('DB_HOST'),
            'PORT': os.getenv('DB_PORT', '5432'),
            "CONN_MAX_AGE": 600,  # Connection pooling
            "OPTIONS": {
                "connect_timeout": 10,
            },
        }
    }



# Redis Configuration
REDIS_HOST = os.getenv('REDIS_HOST', 'redis')
REDIS_PORT = os.getenv('REDIS_PORT', '6379')


# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


AUTH_USER_MODEL = 'users.User'


# # Security Settings (Data Encryption)
# SECURE_SSL_REDIRECT = os.getenv('SECURE_SSL_REDIRECT')
# SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE')
# CSRF_COOKIE_SECURE = os.getenv('CSRF_COOKIE_SECURE')


SITE_ID = 1
FRONTEND_LOGIN_ERROR_URL = os.getenv('FRONTEND_LOGIN_ERROR_URL')
FRONTEND_LOGIN_SUCCESS_URL = os.getenv('FRONTEND_LOGIN_SUCCESS_URL')

# Google OAuth2 Settings
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
GOOGLE_REDIRECT_URI = os.getenv('GOOGLE_REDIRECT_URI')
 # for mobile
GOOGLE_WEB_CLIENT_ID = os.getenv('GOOGLE_WEB_CLIENT_ID')

if DEBUG:
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    

# Apple OAuth
# APPLE_TEAM_ID = os.getenv('APPLE_TEAM_ID')
# APPLE_PRIVATE_KEY = os.getenv('APPLE_PRIVATE_KEY')
# APPLE_KEY_ID = os.getenv('APPLE_KEY_ID')
APPLE_CLIENT_ID = os.getenv('APPLE_CLIENT_ID')
# APPLE_REDIRECT_URI = os.getenv('APPLE_REDIRECT_URI')



# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

# Static files — always served from local volume via Nginx
STATIC_URL  = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# ── Media / File Storage ─────────────────────────────────────────────────────
# In production (DEBUG=False): media files go to AWS S3.
# In development (DEBUG=True):  media files stay on local filesystem.
#
# Required env vars for S3 (set in .env.production):
#   AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_STORAGE_BUCKET_NAME,
#   AWS_S3_REGION_NAME (e.g. eu-north-1)

_USE_S3 = os.getenv('USE_S3', 'False') == 'True'

if _USE_S3:
    # ── AWS S3 Configuration ─────────────────────────────────────────────
    AWS_ACCESS_KEY_ID       = os.getenv('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY   = os.getenv('AWS_SECRET_ACCESS_KEY')
    AWS_STORAGE_BUCKET_NAME = os.getenv('AWS_STORAGE_BUCKET_NAME')
    AWS_S3_REGION_NAME      = os.getenv('AWS_S3_REGION_NAME', 'eu-north-1')
    AWS_S3_CUSTOM_DOMAIN    = f'{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com'
    AWS_S3_FILE_OVERWRITE   = False    # Don't overwrite files with same name
    AWS_DEFAULT_ACL         = None     # Use bucket policy, not object ACL
    AWS_S3_OBJECT_PARAMETERS = {
        'CacheControl': 'max-age=86400',
    }

    # Media files → S3
    STORAGES = {
        'default': {
            'BACKEND': 'storages.backends.s3boto3.S3Boto3Storage',
            'OPTIONS': {
                'bucket_name': AWS_STORAGE_BUCKET_NAME,
                'location': 'media',          # Files go into /media/ prefix in bucket
                'file_overwrite': False,
            },
        },
        # Static files → local (served by Nginx from Docker volume)
        'staticfiles': {
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    }

    MEDIA_URL  = f'https://{AWS_S3_CUSTOM_DOMAIN}/media/'
    MEDIA_ROOT = None   # Not used when storing on S3

    # CKEditor 5 uploads → S3
    CKEDITOR_5_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'

else:
    # ── Local filesystem (development) ──────────────────────────────────
    MEDIA_URL  = '/media/'
    MEDIA_ROOT = BASE_DIR / 'media'
    # CKEditor 5 uploads → local
    CKEDITOR_5_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'



# Application URLs
BASE_URL = os.getenv('BASE_URL', 'http://127.0.0.1:8000/')
FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:3000')


# Rest Framework settings
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        #'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.OrderingFilter',
        'rest_framework.filters.SearchFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'core.pagination.FlexiblePageNumberPagination',
    'PAGE_SIZE': 8,
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.FormParser',
        'rest_framework.parsers.MultiPartParser',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    
}


# drf-spectacular settings
SPECTACULAR_SETTINGS = {
    'TITLE': 'A Muslim Matchmaker (AMM) API',
    'DESCRIPTION': (
        'API for A Muslim Matchmaker — a trusted matrimonial platform for conservative Sunni Muslims. '
        'Provides endpoints for authentication, profile management, connection requests, matches, '
        'notifications, chat, and private matchmaking.'
    ),
    'VERSION': '1.0.0',
    'TERMS_OF_SERVICE': '',
    'CONTACT': {'email': 'support@amuslimmatrimony.com'},
    'LICENSE': {'name': 'Proprietary'},
    'SERVE_INCLUDE_SCHEMA': False,
    
    # Postman friendly settings
    'COMPONENT_SPLIT_REQUEST': True,
    #'POSTMAN_ENABLED': True,
    'SORT_OPERATIONS': False,
    
}


# Jazzmin settings
JAZZMIN_SETTINGS = {
    "site_title": "AMM Admin",
    "site_header": "A Muslim Matchmaker",
    "site_brand": "AMM",
    "welcome_sign": "Welcome to the AMM Admin Panel",
    "copyright": "A Muslim Matchmaker © 2026",
    "user_avatar": None,
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "auth.Group": "fas fa-users",
    },
    "default_icon_parents": "fas fa-chevron-right",
    "default_icon_children": "fas fa-circle",
}


JAZZMIN_UI_TWEAKS = {
    "theme": "lux",
    "dark_mode_theme": "darkly",
    "navbar_small_text": False,
    "footer_small_text": False,
    "body_small_text": False,
    "brand_color": "primary",
    "accent": "primary",
    "navbar": "navbar-dark bg-primary",
    "no_navbar_border": False,
}


SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
   
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'VERIFYING_KEY': None,
    'AUDIENCE': None,
    'ISSUER': None,
   
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'USER_AUTHENTICATION_RULE': 'rest_framework_simplejwt.authentication.default_user_authentication_rule',
   
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
   
    'JTI_CLAIM': 'jti',
}


# Celery Configs
CELERY_BROKER_URL = 'redis://{host}:{port}/0'.format(
    host=os.environ.get('REDIS_HOST') or 'localhost',
    port=os.environ.get('REDIS_PORT') or '6379',
)  # message broker
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
CELERY_ACCEPT_CONTENT = ['json']  # Celery will only accept tasks serialized as JSON.
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True  # Celery tracks when a task starts executing.
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes


# ── And the Redis cache section ───────────────────────────────────────────
_REDIS_HOST = os.environ.get('REDIS_HOST') or 'localhost'
_REDIS_PORT = os.environ.get('REDIS_PORT') or '6379'
_REDIS_CACHE_DB = os.environ.get('REDIS_CACHE_DB', '1')
_REDIS_CHANNEL_DB = os.environ.get('REDIS_CHANNEL_DB', '2')
_REDIS_SOCKET_TIMEOUT = float(os.environ.get('REDIS_SOCKET_TIMEOUT', '30'))
_REDIS_SOCKET_CONNECT_TIMEOUT = float(os.environ.get('REDIS_SOCKET_CONNECT_TIMEOUT', '30'))
_REDIS_HEALTH_CHECK_INTERVAL = int(os.environ.get('REDIS_HEALTH_CHECK_INTERVAL', '30'))

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': f'redis://{_REDIS_HOST}:{_REDIS_PORT}/{_REDIS_CACHE_DB}',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'SOCKET_TIMEOUT': _REDIS_SOCKET_TIMEOUT,
            'SOCKET_CONNECT_TIMEOUT': _REDIS_SOCKET_CONNECT_TIMEOUT,
            'RETRY_ON_TIMEOUT': True,
            'HEALTH_CHECK_INTERVAL': _REDIS_HEALTH_CHECK_INTERVAL,
        },
        'KEY_PREFIX': 'amm',   # Adds a prefix to every cache key.
        'TIMEOUT': 300,  # Default cache expiry time = 300s (5 mins).
    }
}

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [
                {
                    "address": f"redis://{_REDIS_HOST}:{_REDIS_PORT}/{_REDIS_CHANNEL_DB}",
                    "socket_timeout": _REDIS_SOCKET_TIMEOUT,
                    "socket_connect_timeout": _REDIS_SOCKET_CONNECT_TIMEOUT,
                    "retry_on_timeout": True,
                    "health_check_interval": _REDIS_HEALTH_CHECK_INTERVAL,
                }
            ],
            "capacity": 1500,
            "expiry": 60,
            "group_expiry": 86400,
        },
    },
}


# Email Configs 
EMAIL_BACKEND       = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
EMAIL_HOST          = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT          = int(os.getenv('EMAIL_PORT', 587))
EMAIL_USE_TLS       = os.getenv('EMAIL_USE_TLS', 'True') == 'True'
EMAIL_HOST_USER     = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL  = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@amuslimmatrimony.com')


# OTP lifetimes (seconds)
OTP_EXPIRY_SECONDS                  = int(os.getenv("OTP_EXPIRY_SECONDS", "300"))
PASSWORD_RESET_OTP_EXPIRY_SECONDS   = int(os.getenv("PASSWORD_RESET_OTP_EXPIRY_SECONDS", "600"))
PASSWORD_RESET_TOKEN_EXPIRY_SECONDS = int(os.getenv("PASSWORD_RESET_TOKEN_EXPIRY_SECONDS", "900"))

# New — controls how often LastActiveMiddleware writes to DB (seconds)
LAST_ACTIVE_UPDATE_INTERVAL = int(os.getenv("LAST_ACTIVE_UPDATE_INTERVAL", "120"))  # 2 min

# CKEditor 5 Configuration
CKEDITOR_5_CONFIGS = {
    'default': {
        'toolbar': [
            'heading', '|',
            'bold', 'italic', 'link', 'bulletedList', 'numberedList', '|',
            'blockQuote', 'insertTable', '|',
            'undo', 'redo'
        ],
        'height': 300,
        'width': '100%',
    },
    'extends': {
        'blockToolbar': [
            'paragraph', 'heading1', 'heading2', 'heading3', '|',
            'bulletedList', 'numberedList', '|',
            'blockQuote',
        ],
        'toolbar': [
            'heading', '|',
            'outdent', 'indent', '|',
            'bold', 'italic', 'link', 'underline', 'strikethrough',
            'code', 'subscript', 'superscript', 'highlight', '|',
            'codeBlock', 'sourceEditing', 'insertImage',
            'bulletedList', 'numberedList', 'todoList', '|',
            'blockQuote', 'imageUpload', '|',
            'fontSize', 'fontFamily', 'fontColor', 'fontBackgroundColor',
            'mediaEmbed', 'removeFormat', 'insertTable',
        ],
        'image': {
            'toolbar': [
                'imageTextAlternative', '|',
                'imageStyle:alignLeft',
                'imageStyle:alignRight',
                'imageStyle:alignCenter',
                'imageStyle:side', '|'
            ],
            'styles': [
                'full',
                'side',
                'alignLeft',
                'alignRight',
                'alignCenter',
            ]
        },
        'table': {
            'contentToolbar': [
                'tableColumn', 'tableRow', 'mergeTableCells',
                'tableProperties', 'tableCellProperties'
            ],
            'tableProperties': {
                'borderColors': [],
                'backgroundColors': []
            },
            'tableCellProperties': {
                'borderColors': [],
                'backgroundColors': []
            }
        },
        'heading': {
            'options': [
                {'model': 'paragraph', 'title': 'Paragraph', 'class': 'ck-heading_paragraph'},
                {'model': 'heading1', 'view': 'h1', 'title': 'Heading 1', 'class': 'ck-heading_heading1'},
                {'model': 'heading2', 'view': 'h2', 'title': 'Heading 2', 'class': 'ck-heading_heading2'},
                {'model': 'heading3', 'view': 'h3', 'title': 'Heading 3', 'class': 'ck-heading_heading3'}
            ]
        }
    },
    'list': {
        'properties': {
            'styles': 'true',
            'startIndex': 'true',
            'reversed': 'true',
        }
    }
}

# CKEditor 5 file upload settings
CKEDITOR_5_UPLOAD_PATH = "uploads/"
# Note: CKEDITOR_5_FILE_STORAGE is set dynamically above in the media/storage section


# ── Logging ───────────────────────────────────────────────────────────────────
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'WARNING' if not DEBUG else 'INFO',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
        'celery': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'storages': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}



# Firebase Configuration
# FIREBASE_CREDENTIALS_PATH = os.path.join(BASE_DIR, 'firebase-credentials.json')

# # Initialize Firebase Admin SDK
# if os.path.exists(FIREBASE_CREDENTIALS_PATH):
#     cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
#     firebase_admin.initialize_app(cred)
# else:
#     print("WARNING: Firebase credentials not found. Push notifications disabled.")

# Channels Configuration (for WebSocket)
ASGI_APPLICATION = 'core.asgi.application'


# Verification Service Configuration
# VERIFICATION_BASE_URL = os.getenv("VERIFICATION_BASE_URL", "https://document-verification-ai-chatbot.onrender.com")
# VERIFICATION_ENDPOINT = f"{VERIFICATION_BASE_URL}/api/passport/verify"
# AI_REQUEST_TIMEOUT    = 30


# iOS In-App Purchase Configuration
# IOS_SHARED_SECRET = os.getenv('IOS_SHARED_SECRET', '')
# IOS_SANDBOX_MODE = os.getenv('IOS_SANDBOX_MODE', 'True') == 'True'

# # Android In-App Purchase Configuration
# ANDROID_PACKAGE_NAME = os.getenv('ANDROID_PACKAGE_NAME', 'com.autointel.vehicle')
# GOOGLE_PLAY_SERVICE_ACCOUNT_FILE = os.path.join(BASE_DIR, 'google-play-service-account.json')

