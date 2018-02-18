# -*- encoding: utf-8 -*-
import datetime
import json
import logging

import os
from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth import login as djangologin
from django.contrib.auth import logout as djangologout
from django.core.mail import send_mail, mail_admins

from chat.templatetags.md5url import md5url

try:
	from django.template.context_processors import csrf
except ImportError:
	from django.core.context_processors import csrf
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import transaction
from django.db.models import Count, Q, F
from django.http import Http404
from django.utils.timezone import utc
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.views.decorators.http import require_http_methods
from django.views.generic import View
from chat import utils
from chat.decorators import login_required_no_redirect
from chat.forms import UserProfileForm, UserProfileReadOnlyForm
from chat.models import Issue, IssueDetails, IpAddress, UserProfile, Verification, Message, Subscription, \
	SubscriptionMessages, RoomUsers
from django.conf import settings
from chat.utils import hide_fields, check_user, check_password, check_email, extract_photo, send_sign_up_email, \
	create_user_model, check_captcha, send_reset_password_email, get_client_ip, get_or_create_ip

logger = logging.getLogger(__name__)
RECAPTCHA_SITE_KEY = getattr(settings, "RECAPTCHA_SITE_KEY", None)
RECAPTHCA_SITE_URL = getattr(settings, "RECAPTHCA_SITE_URL", None)
GOOGLE_OAUTH_2_CLIENT_ID = getattr(settings, "GOOGLE_OAUTH_2_CLIENT_ID", None)
GOOGLE_OAUTH_2_JS_URL = getattr(settings, "GOOGLE_OAUTH_2_JS_URL", None)
FACEBOOK_APP_ID = getattr(settings, "FACEBOOK_APP_ID", None)
FACEBOOK_JS_URL = getattr(settings, "FACEBOOK_JS_URL", None)

# TODO doesn't work
def handler404(request):
	return HttpResponse("Page not found", content_type='text/plain')


@require_http_methods(['POST'])
def validate_email(request):
	"""
	POST only, validates email during registration
	"""
	email = request.POST.get('email')
	try:
		utils.check_email(email)
		response = settings.VALIDATION_IS_OK
	except ValidationError as e:
		response = e.message
	return HttpResponse(response, content_type='text/plain')


@require_http_methods(['POST'])
@login_required_no_redirect(False)
def save_room_settings(request):
	"""
	POST only, validates email during registration
	"""
	logger.debug('save_room_settings request,  %s', request.POST)
	room_id = request.POST['roomId']
	updated = RoomUsers.objects.filter(room_id=room_id, user_id=request.user.id).update(
		volume=request.POST['volume'],
		notifications=request.POST['notifications'] == 'true',
	)
	return HttpResponse(settings.VALIDATION_IS_OK if updated == 1 else "Nothing updated", content_type='text/plain')


@require_http_methods('GET')
@transaction.atomic
def get_firebase_playback(request):
	registration_id = request.META['HTTP_AUTH']
	logger.debug('Firebase playback, id %s', registration_id)
	query_sub_message = SubscriptionMessages.objects.filter(subscription__registration_id=registration_id, received=False).order_by('-message__time')[:1]
	sub_message = query_sub_message[0]
	SubscriptionMessages.objects.filter(id=sub_message.id).update(received=True)
	message = Message.objects.select_related("sender__username", "room__name").get(id=sub_message.message_id)
	data = {
		'title': message.sender.username,
		'options': {
			'body': message.content,
			'icon': md5url('images/favicon.ico'),
			'data': {
				'id': sub_message.message_id,
				'sender': message.sender.username,
				'room': message.room.name,
				'roomId': message.room_id
			},
			'requireInteraction': True
		},
	}
	return HttpResponse(json.dumps(data), content_type='application/json')


def test(request):
	return HttpResponse(settings.VALIDATION_IS_OK, content_type='text/plain')


@require_http_methods('POST')
def register_subscription(request):
	logger.debug('Subscription request,  %s', request)
	registration_id = request.POST['registration_id']
	agent = request.POST['agent']
	is_mobile = request.POST['is_mobile']
	ip = get_or_create_ip(get_client_ip(request), logger)
	Subscription.objects.update_or_create(
		registration_id=registration_id,
		defaults={
			'user': request.user,
			'inactive': False,
			'updated': datetime.datetime.now(),
			'agent': agent,
			'is_mobile': is_mobile == 'true',
			'ip': ip
		}
	)
	return HttpResponse(settings.VALIDATION_IS_OK, content_type='text/plain')

@require_http_methods('POST')
def validate_user(request):
	"""
	Validates user during registration
	"""
	try:
		username = request.POST.get('username')
		utils.check_user(username)
		# hardcoded ok check in register.js
		message = settings.VALIDATION_IS_OK
	except ValidationError as e:
		message = e.message
	return HttpResponse(message, content_type='text/plain')


def get_service_worker(request):  # this stub is only for development, this is replaced in nginx for prod
	worker = open(os.path.join(settings.STATIC_ROOT, 'js', 'sw.js'), 'rb')
	response = HttpResponse(content=worker)
	response['Content-Type'] = 'application/javascript'
	return response

@require_http_methods('GET')
@login_required_no_redirect(False)
def home(request):
	"""
	Login or logout navbar is creates by means of create_nav_page
	@return:  the x intercept of the line M{y=m*x+b}.
	"""
	context = csrf(request)
	up = UserProfile.objects.defer('suggestions', 'highlight_code', 'embedded_youtube', 'online_change_sound', 'incoming_file_call_sound', 'message_sound', 'theme').get(id=request.user.id)
	context['suggestions'] = up.suggestions
	context['highlight_code'] = up.highlight_code
	context['message_sound'] = up.message_sound
	context['incoming_file_call_sound'] = up.incoming_file_call_sound
	context['online_change_sound'] = up.online_change_sound
	context['theme'] = up.theme
	context['embedded_youtube'] = up.embedded_youtube
	context['extensionId'] = settings.EXTENSION_ID
	context['extensionUrl'] = settings.EXTENSION_INSTALL_URL
	context['defaultRoomId'] = settings.ALL_ROOM_ID
	context['manifest'] = hasattr(settings, 'FIREBASE_API_KEY')
	return render_to_response('chat.html', context, context_instance=RequestContext(request))


@login_required_no_redirect(True)
def logout(request):
	"""
	POST. Logs out into system.
	"""
	registration_id = request.POST.get('registration_id')
	if registration_id is not None:
		Subscription.objects.filter(registration_id=registration_id).delete()
	djangologout(request)
	return HttpResponse(settings.VALIDATION_IS_OK, content_type='text/plain')

@require_http_methods(['POST'])
def auth(request):
	"""
	Logs in into system.
	"""
	username = request.POST.get('username')
	password = request.POST.get('password')
	user = authenticate(username=username, password=password)
	if user is not None:
		djangologin(request, user)
		message = settings.VALIDATION_IS_OK
	else:
		message = 'Login or password is wrong'
	logger.debug('Auth request %s ; Response: %s', hide_fields(request.POST, ('password',)), message)
	return HttpResponse(message, content_type='text/plain')


def send_restore_password(request):
	"""
	Sends email verification code
	"""
	logger.debug('Recover password request %s', request)
	try:
		username_or_password = request.POST.get('username_or_password')
		check_captcha(request)
		user_profile = UserProfile.objects.get(Q(username=username_or_password) | Q(email=username_or_password))
		if not user_profile.email:
			raise ValidationError("You didn't specify email address for this user")
		verification = Verification(type_enum=Verification.TypeChoices.password, user_id=user_profile.id)
		verification.save()
		send_reset_password_email(request, user_profile, verification)
		message = settings.VALIDATION_IS_OK
		logger.debug('Verification email has been send for token %s to user %s(id=%d)',
				verification.token, user_profile.username, user_profile.id)
	except UserProfile.DoesNotExist:
		message = "User with this email or username doesn't exist"
		logger.debug("Skipping password recovery request for nonexisting user")
	except (UserProfile.DoesNotExist, ValidationError) as e:
		logger.debug('Not sending verification email because %s', e)
		message = 'Unfortunately we were not able to send you restore password email because {}'.format(e)
	return HttpResponse(message, content_type='text/plain')


def get_html_restore_pass():
	""""""

class RestorePassword(View):

	def get_user_by_code(self, token):
		"""
		:param token: token code to verify
		:type token: str
		:raises ValidationError: if token is not usable
		:return: UserProfile, Verification: if token is usable
		"""
		try:
			v = Verification.objects.get(token=token)
			if v.type_enum != Verification.TypeChoices.password:
				raise ValidationError("it's not for this operation ")
			if v.verified:
				raise ValidationError("it's already used")
			# TODO move to sql query or leave here?
			if v.time < datetime.datetime.utcnow().replace(tzinfo=utc) - datetime.timedelta(days=1):
				raise ValidationError("it's expired")
			return UserProfile.objects.get(id=v.user_id), v
		except Verification.DoesNotExist:
			raise ValidationError('Unknown verification token')

	@transaction.atomic
	def post(self, request):
		"""
		Sends email verification token
		"""
		token = request.POST.get('token', False)
		try:
			logger.debug('Proceed Recover password with token %s', token)
			user, verification = self.get_user_by_code(token)
			password = request.POST.get('password')
			check_password(password)
			user.set_password(password)
			user.save(update_fields=('password',))
			verification.verified = True
			verification.save(update_fields=('verified',))
			logger.info('Password has been change for token %s user %s(id=%d)', token, user.username, user.id)
			response = settings.VALIDATION_IS_OK
		except ValidationError as e:
			logger.debug('Rejecting verification token %s because %s', token, e)
			response = "".join(("You can't reset password with this token because ", str(e)))
		return HttpResponse(response, content_type='text/plain')

	def get(self, request):
		token = request.GET.get('token', False)
		logger.debug('Rendering restore password page with token  %s', token)
		try:
			user = self.get_user_by_code(token)[0]
			response = {
				'message': settings.VALIDATION_IS_OK,
				'restore_user': user.username,
				'token': token
			}
		except ValidationError as e:
			logger.debug('Rejecting verification token %s because %s', token, e)
			response = {'message': "Unable to confirm email with token {} because {}".format(token, e)}
		return render_to_response('reset_password.html', response, context_instance=RequestContext(request))


@require_http_methods('GET')
def confirm_email(request):
	"""
	Accept the verification token sent to email
	"""
	token = request.GET.get('token', False)
	logger.debug('Processing email confirm with token  %s', token)
	try:
		try:
			v = Verification.objects.get(token=token)
		except Verification.DoesNotExist:
			raise ValidationError('Unknown verification token')
		if v.type_enum != Verification.TypeChoices.register:
			raise ValidationError('This is not confirm email token')
		if v.verified:
			raise ValidationError('This verification token already accepted')
		user = UserProfile.objects.get(id=v.user_id)
		if user.email_verification_id != v.id:
			raise ValidationError('Verification token expired because you generated another one')
		v.verified = True
		v.save(update_fields=['verified'])
		message = settings.VALIDATION_IS_OK
		logger.info('Email verification token %s has been accepted for user %s(id=%d)', token, user.username, user.id)
	except Exception as e:
		logger.debug('Rejecting verification token %s because %s', token, e)
		message = ("Unable to confirm email with token {} because {}".format(token, e))
	response = {'message': message}
	return render_to_response('confirm_mail.html', response, context_instance=RequestContext(request))


@require_http_methods('GET')
def show_profile(request, profile_id):
	try:
		user_profile = UserProfile.objects.get(pk=profile_id)
		form = UserProfileReadOnlyForm(instance=user_profile)
		form.username = user_profile.username
		return render_to_response(
			'show_profile.html',
			{'form': form},
			context_instance=RequestContext(request)
		)
	except ObjectDoesNotExist:
		raise Http404


@require_http_methods('GET')
def statistics(request):
	pie_data = IpAddress.objects.values('country').filter(country__isnull=False).annotate(count=Count("country"))
	return HttpResponse(json.dumps(list(pie_data)), content_type='application/json')


@login_required_no_redirect()
@transaction.atomic
def report_issue(request):
	logger.info('Saving issue: %s', hide_fields(request.POST, ('log',), huge=True))
	issue_text = request.POST['issue']
	issue = Issue.objects.get_or_create(content=issue_text)[0]
	issue_details = IssueDetails(
		sender_id=request.user.id,
		browser=request.POST.get('browser'),
		issue=issue,
		log=request.POST.get('log')
	)
	try:
		mail_admins("{} reported issue".format(request.user.username), issue_text, fail_silently=True)
	except Exception as e:
		logging.error("Failed to send issue email because {}".format(e))
	issue_details.save()
	return HttpResponse(settings.VALIDATION_IS_OK, content_type='text/plain')


class ProfileView(View):

	@login_required_no_redirect()
	def get(self, request):
		user_profile = UserProfile.objects.get(pk=request.user.id)
		form = UserProfileForm(instance=user_profile)
		c = csrf(request)
		c['form'] = form
		c['date_format'] = settings.DATE_INPUT_FORMATS_JS
		return render_to_response('change_profile.html', c, context_instance=RequestContext(request))

	@login_required_no_redirect()
	def post(self, request):
		logger.info('Saving profile: %s', hide_fields(request.POST, ("base64_image", ), huge=True))
		user_profile = UserProfile.objects.get(pk=request.user.id)
		image_base64 = request.POST.get('base64_image')

		if image_base64 is not None:
			image = extract_photo(image_base64)
			request.FILES['photo'] = image

		form = UserProfileForm(request.POST, request.FILES, instance=user_profile)
		if form.is_valid():
			profile = form.save()
			response = profile. photo.url if 'photo' in  request.FILES else settings.VALIDATION_IS_OK
		else:
			response = form.errors
		return HttpResponse(response, content_type='text/plain')


class RegisterView(View):

	def get(self, request):
		logger.debug(
			'Rendering register page with captcha site key %s and oauth key %s',
			RECAPTCHA_SITE_KEY, GOOGLE_OAUTH_2_CLIENT_ID
		)
		c = csrf(request)
		c['captcha_key'] = RECAPTCHA_SITE_KEY
		c['captcha_url'] = RECAPTHCA_SITE_URL
		c['oauth_url'] = GOOGLE_OAUTH_2_JS_URL
		c['oauth_token'] = GOOGLE_OAUTH_2_CLIENT_ID
		c['fb_app_id'] = FACEBOOK_APP_ID
		c['fb_js_url'] = FACEBOOK_JS_URL
		return render_to_response("register.html", c, context_instance=RequestContext(request))

	@transaction.atomic
	def post(self, request):
		try:
			rp = request.POST
			logger.info('Got register request %s', hide_fields(rp, ('password', 'repeatpassword')))
			(username, password, email) = (rp.get('username'), rp.get('password'), rp.get('email'))
			check_user(username)
			check_password(password)
			check_email(email)
			user_profile = UserProfile(username=username, email=email, sex_str=rp.get('sex'))
			user_profile.set_password(password)
			create_user_model(user_profile)
			# You must call authenticate before you can call login
			auth_user = authenticate(username=username, password=password)
			message = settings.VALIDATION_IS_OK  # redirect
			if email:
				send_sign_up_email(user_profile, request.get_host(), request)
			djangologin(request, auth_user)
		except ValidationError as e:
			message = e.message
			logger.debug('Rejecting request because "%s"', message)
		return HttpResponse(message, content_type='text/plain')
