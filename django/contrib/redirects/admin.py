from django.conf import settings
from django.contrib import admin
from django.contrib.redirects import get_redirect_model


class RedirectAdmin(admin.ModelAdmin):
    list_display = ('old_path', 'new_path')
    search_fields = ('old_path', 'new_path')

    if settings.REDIRECT_MODEL == 'redirects.Redirect':
        list_filter = ('site',)
        radio_fields = {'site': admin.VERTICAL}

admin.site.register(get_redirect_model(), RedirectAdmin)
