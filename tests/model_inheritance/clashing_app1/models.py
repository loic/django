from django.db import models
from django.utils.encoding import python_2_unicode_compatible

from model_inheritance.tests import clashing_apps


class Title(models.Model):
    title = models.CharField(max_length=50)

    class Meta:
        apps = clashing_apps


class NamedURL(models.Model):
    title = models.ForeignKey(Title, related_name='attached_%(app_label)s_%(class)s_set')
    url = models.URLField()

    class Meta:
        abstract = True
        apps = clashing_apps


@python_2_unicode_compatible
class Copy(NamedURL):
    content = models.TextField()

    def __str__(self):
        return self.content

    class Meta:
        apps = clashing_apps
