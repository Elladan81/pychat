### RENAME THIS FILE to production py

DEBUG = False
TEMPLATE_DEBUG = False

### Replace with your django secret key, you can use https://www.miniwebtool.com/django-secret-key-generator/ to generate one
SECRET_KEY = '**************************************************'

### If you use ClodFlare, you may want to serve static files via it.
### I wouldn't recommend to put everything under CloudFlare, your sockect connection will strugle!
### Instead you
# STATIC_URL = 'https://static.pychat.org/'
# MEDIA_URL = "https://static.pychat.org/photo/"


# this this emails settings will be used to send emails. E.g. when user restores password via email.
import os

EMAIL_USE_TLS = True
EMAIL_HOST = 'localhost' # For gmail settings example 'smtp.gmail.com'
EMAIL_PORT = 25 # google smpt port '587'
EMAIL_HOST_USER = '' # you gmail username e.g. 'chat.django@gmail.com'
EMAIL_HOST_PASSWORD = '' # Your gmail password  e.g. 'Ilovepython'
SERVER_EMAIL = 'root@pychat.org'
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
ADMINS = [('YourName', 'emailAddresThatYouWillReceiveReportsOn@gmail.com'), ]


REDIS_PORT = int(os.environ.get('REDIS_PORT', '6379'))
REDIS_HOST = os.environ.get('REDIS_HOST', 'db')
DATABASES = {
	'default': {
		'ENGINE': 'django.db.backends.mysql',  # django.db.backends.sqlite3
		'NAME': os.environ.get('MYSQL_DATABASE', 'pychat'),
		'USER': os.environ.get('MYSQL_USER', 'root'),
		'PASSWORD': os.environ.get('MYSQL_PASSWORD', ''),
		'HOST': os.environ.get('MYSQL_HOST', 'localhost'),
		'PORT': os.environ.get('MYSQL_PORT', '3306'),  # mysql uses socket if host is localhost
		'OPTIONS': {
			'autocommit': True,
		},
	}
}



### Pychat also supports https://developers.google.com/web/fundamentals/push-notifications/ firebase notifications, like in facebook.
### They will fire even user doesn't have opened tab. That can be turned on/off by used in his/her profile with checkbox `Notifications`.
### The implementation is similar like https://github.com/GoogleChrome/samples/tree/gh-pages/push-messaging-and-notifications.
###    1. Create a project on the Firebase Developer Console: https://console.firebase.google.com/
###    2. Go to Settings (the cog near the top left corner), click the Cloud Messaging Tab: https://console.firebase.google.com/u/1/project/pychat-org/settings/cloudmessaging/
###    3. Put `<Your Cloud Messaging API Key ...>` to `FIREBASE_API_KEY` below.
###    4. Create `chat/static/manifest.json` with content like https://github.com/GoogleChrome/samples/blob/gh-pages/push-messaging-and-notifications/manifest.sample.json:
###
### {
###  "name": "Pychat Push Notifications",
###  "short_name": "PyPush",
###  "start_url": "/",
###  "display": "standalone",
###  "gcm_sender_id": "<Your Sender ID from https://console.firebase.google.com>"
### }
FIREBASE_API_KEY = '***********:********************************************************************************************************************************************'


# If you want to use giphy images that appears if user types "/giphy example".
# To get those -sign up in https://developers.giphy.com/, create a new app and replaced with its key.
GIPHY_API_KEY = '********************************'


### If you want recaptcha:
### Open https://www.google.com/recaptcha/admin#list and register new domain
RECAPTCHA_SITE_KEY = '****************************************' # REPLACE_THIS_WITH_DATA-SITEKEY_DIV_ATTRIBUTE
RECAPTCHA_SECRET_KEY = '****************************************' # REPLACE_THIS_WITH_KEY_FOR_RETRIEVING_RESULT


# For google auth follow the instructions here https://developers.google.com/identity/sign-in/web/devconsole-project
GOOGLE_OAUTH_2_CLIENT_ID = 'YOUR_CLIENT_ID.apps.googleusercontent.com'

FACEBOOK_ACCESS_TOKEN = '***************|***************************' # https://developers.facebook.com/tools/access_token/
FACEBOOK_APP_ID = '16_NUMBER_APP_ID' # https://developers.facebook.com/apps/
GOOGLE_OAUTH_2_HOST = 'pychat.org'