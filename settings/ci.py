from ecommerce.settings.hyperpay import *

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'test_ecommerce',
        'USER': 'root',
        'PASSWORD': 'password',
        'HOST': '127.0.0.1',
        'PORT': '3306',
        'ATOMIC_REQUESTS': True,
        'CONN_MAX_AGE': 60,
    }
}
