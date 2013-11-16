from __future__ import unicode_literals

from django.conf import settings
from django.contrib.redirects import get_redirect_model
from django.contrib.sites.models import get_current_site
from django.core.exceptions import ImproperlyConfigured
from django import http


class RedirectFallbackMiddleware(object):

    # Defined as class-level attributes to be subclassing-friendly.
    response_gone_class = http.HttpResponseGone
    response_redirect_class = http.HttpResponsePermanentRedirect

    def __init__(self):
        if (settings.REDIRECT_MODEL == 'redirects.Redirect' and
                'django.contrib.sites' not in settings.INSTALLED_APPS):
            raise ImproperlyConfigured(
                "You cannot use RedirectFallbackMiddleware when "
                "django.contrib.sites is not installed."
            )

    def process_response(self, request, response):
        # No need to check for a redirect for non-404 responses.
        if response.status_code != 404:
            return response

        full_path = request.get_full_path()

        redirect_model = get_redirect_model()

        extra = {}
        if settings.REDIRECT_MODEL == 'redirects.Redirect':
            extra['site'] = get_current_site(request)

        r = None
        try:
            r = redirect_model.objects.get(old_path=full_path, **extra)
        except redirect_model.DoesNotExist:
            pass
        if settings.APPEND_SLASH and not request.path.endswith('/'):
            # Try appending a trailing slash.
            path_len = len(request.path)
            full_path = full_path[:path_len] + '/' + full_path[path_len:]
            try:
                r = redirect_model.objects.get(old_path=full_path, **extra)
            except redirect_model.DoesNotExist:
                pass
        if r is not None:
            if r.new_path == '':
                return self.response_gone_class()
            return self.response_redirect_class(r.new_path)

        # No redirect was found. Return the response.
        return response
