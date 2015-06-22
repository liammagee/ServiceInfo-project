from service_info.settings.base import *  # noqa

os.environ.setdefault('CACHE_HOST', '127.0.0.1:11211')

DEBUG = False
TEMPLATE_DEBUG = DEBUG

DATABASES['default']['NAME'] = 'service_info_testing'
DATABASES['default']['USER'] = 'service_info_testing'
DATABASES['default']['HOST'] = os.environ.get('DB_HOST', '')
DATABASES['default']['PORT'] = os.environ.get('DB_PORT', '')
DATABASES['default']['PASSWORD'] = os.environ['DB_PASSWORD']

WEBSERVER_ROOT = '/var/www/service_info/'

PUBLIC_ROOT = os.path.join(WEBSERVER_ROOT, 'public')

STATIC_ROOT = os.path.join(PUBLIC_ROOT, 'static')

MEDIA_ROOT = os.path.join(PUBLIC_ROOT, 'media')

LOGGING['handlers']['file']['filename'] = os.path.join(WEBSERVER_ROOT, 'log', 'service_info.log')

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.memcached.MemcachedCache',
        'LOCATION': '%(CACHE_HOST)s' % os.environ,
    }
}

EMAIL_SUBJECT_PREFIX = '[ServiceInfo Testing] '

SESSION_COOKIE_SECURE = True

SESSION_COOKIE_HTTPONLY = True

ALLOWED_HOSTS = os.environ['ALLOWED_HOSTS'].split(';')

SITE_ID = TESTING_SITE_ID

# Uncomment if using celery worker configuration
if 'BROKER_PASSWORD' in os.environ:
    CELERY_SEND_TASK_ERROR_EMAILS = True
    os.environ.setdefault('BROKER_HOST', '127.0.0.1:5672')
    BROKER_URL = 'amqp://service_info_testing:%(BROKER_PASSWORD)s@%(BROKER_HOST)s' \
                 '/service_info_testing' % os.environ

# testing JIRA projects:
JIRA_SERVICES_PROJECT_KEY = 'QASM'
JIRA_FEEDBACK_PROJECT_KEY = 'QALBF'
