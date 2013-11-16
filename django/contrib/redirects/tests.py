from django import http
from django.conf import settings
from django.contrib.redirects import get_redirect_model
from django.contrib.sites.models import Site
from django.core.exceptions import ImproperlyConfigured
from django.db import IntegrityError
from django.test import TestCase
from django.test.utils import override_settings
from django.utils import six

from .middleware import RedirectFallbackMiddleware
from .models import Redirect, RedirectNoSite


@override_settings(
    APPEND_SLASH=False,
    MIDDLEWARE_CLASSES=list(settings.MIDDLEWARE_CLASSES) +
    ['django.contrib.redirects.middleware.RedirectFallbackMiddleware'],
    SITE_ID=1,
)
class RedirectTests(TestCase):

    def setUp(self):
        self.site = Site.objects.get(pk=settings.SITE_ID)

    def test_model(self):
        r1 = Redirect.objects.create(
            site=self.site, old_path='/initial', new_path='/new_target')
        self.assertEqual(six.text_type(r1), "/initial ---> /new_target")

    def test_duplicates(self):
        Redirect.objects.create(
            site=self.site, old_path='/initial', new_path='/new_target')

        with self.assertRaises(IntegrityError):
            Redirect.objects.create(
                site=self.site, old_path='/initial', new_path='/new_target')

    def test_redirect(self):
        Redirect.objects.create(
            site=self.site, old_path='/initial', new_path='/new_target')
        response = self.client.get('/initial')
        self.assertRedirects(response,
            '/new_target', status_code=301, target_status_code=404)

    @override_settings(APPEND_SLASH=True)
    def test_redirect_with_append_slash(self):
        Redirect.objects.create(
            site=self.site, old_path='/initial/', new_path='/new_target/')
        response = self.client.get('/initial')
        self.assertRedirects(response,
            '/new_target/', status_code=301, target_status_code=404)

    @override_settings(APPEND_SLASH=True)
    def test_redirect_with_append_slash_and_query_string(self):
        Redirect.objects.create(
            site=self.site, old_path='/initial/?foo', new_path='/new_target/')
        response = self.client.get('/initial?foo')
        self.assertRedirects(response,
            '/new_target/', status_code=301, target_status_code=404)

    def test_response_gone(self):
        """When the redirect target is '', return a 410"""
        Redirect.objects.create(
            site=self.site, old_path='/initial', new_path='')
        response = self.client.get('/initial')
        self.assertEqual(response.status_code, 410)

    @override_settings(
        INSTALLED_APPS=[app for app in settings.INSTALLED_APPS
                        if app != 'django.contrib.sites'])
    def test_sites_not_installed(self):
        with self.assertRaises(ImproperlyConfigured):
            RedirectFallbackMiddleware()


@override_settings(
    APPEND_SLASH=False,
    MIDDLEWARE_CLASSES=list(settings.MIDDLEWARE_CLASSES) +
    ['django.contrib.redirects.middleware.RedirectFallbackMiddleware'],
    REDIRECT_MODEL='redirects.RedirectNoSite',

)
class RedirectNoSiteTests(TestCase):
    def setUp(self):
        self.redirect_model = get_redirect_model()


    def test_model(self):
        r1 = self.redirect_model.objects.create(
            old_path='/initial', new_path='/new_target')
        self.assertEqual(six.text_type(r1), "/initial ---> /new_target")

    def test_duplicates(self):
        self.redirect_model.objects.create(old_path='/initial', new_path='/new_target')

        with self.assertRaises(IntegrityError):
            self.redirect_model.objects.create(old_path='/initial', new_path='/new_target')

    def test_redirect(self):
        self.redirect_model.objects.create(
            old_path='/initial', new_path='/new_target')
        response = self.client.get('/initial')
        self.assertRedirects(response,
            '/new_target', status_code=301, target_status_code=404)

    @override_settings(APPEND_SLASH=True)
    def test_redirect_with_append_slash(self):
        self.redirect_model.objects.create(
            old_path='/initial/', new_path='/new_target/')
        response = self.client.get('/initial')
        self.assertRedirects(response,
            '/new_target/', status_code=301, target_status_code=404)

    @override_settings(APPEND_SLASH=True)
    def test_redirect_with_append_slash_and_query_string(self):
        self.redirect_model.objects.create(
            old_path='/initial/?foo', new_path='/new_target/')
        response = self.client.get('/initial?foo')
        self.assertRedirects(response,
            '/new_target/', status_code=301, target_status_code=404)

    def test_response_gone(self):
        """When the redirect target is '', return a 410"""
        self.redirect_model.objects.create(
            old_path='/initial', new_path='')
        response = self.client.get('/initial')
        self.assertEqual(response.status_code, 410)

    @override_settings(
        INSTALLED_APPS=[app for app in settings.INSTALLED_APPS
                        if app != 'django.contrib.sites'])
    def test_sites_not_installed(self):
        RedirectFallbackMiddleware()


class OverriddenRedirectFallbackMiddleware(RedirectFallbackMiddleware):
    # Use HTTP responses different from the defaults
    response_gone_class = http.HttpResponseForbidden
    response_redirect_class = http.HttpResponseRedirect


@override_settings(
    MIDDLEWARE_CLASSES=list(settings.MIDDLEWARE_CLASSES) +
    ['django.contrib.redirects.tests.OverriddenRedirectFallbackMiddleware'],
    SITE_ID=1,
)
class OverriddenRedirectMiddlewareTests(TestCase):

    def setUp(self):
        self.site = Site.objects.get(pk=settings.SITE_ID)

    def test_response_gone_class(self):
        Redirect.objects.create(
            site=self.site, old_path='/initial/', new_path='')
        response = self.client.get('/initial/')
        self.assertEqual(response.status_code, 403)

    def test_response_redirect_class(self):
        Redirect.objects.create(
            site=self.site, old_path='/initial/', new_path='/new_target/')
        response = self.client.get('/initial/')
        self.assertEqual(response.status_code, 302)
