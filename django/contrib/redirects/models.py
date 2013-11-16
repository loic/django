from django.db import models
from django.contrib.sites.models import Site
from django.utils.translation import ugettext_lazy as _
from django.utils.encoding import python_2_unicode_compatible


@python_2_unicode_compatible
class AbstractRedirect(models.Model):
    old_path = models.CharField(_('redirect from'), max_length=200, db_index=True,
        help_text=_("This should be an absolute path, excluding the domain name. Example: '/events/search/'."))
    new_path = models.CharField(_('redirect to'), max_length=200, blank=True,
        help_text=_("This can be either an absolute path (as above) or a full URL starting with 'http://'."))

    class Meta:
        verbose_name = _('redirect')
        verbose_name_plural = _('redirects')
        ordering = ('old_path',)
        abstract = True

    def __str__(self):
        return "%s ---> %s" % (self.old_path, self.new_path)


class RedirectNoSite(AbstractRedirect):
    class Meta(AbstractRedirect.Meta):
        abstract = False
        unique_together = ('old_path',)
        db_table = 'django_redirect_nosite'


class Redirect(AbstractRedirect):
    site = models.ForeignKey(Site)

    class Meta(AbstractRedirect.Meta):
        abstract = False
        unique_together = (('site', 'old_path'),)
        db_table = 'django_redirect'
        swappable = 'REDIRECT_MODEL'
