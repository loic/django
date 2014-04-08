from django.db import models
from django.utils.encoding import python_2_unicode_compatible

from model_inheritance.tests import clashing_apps

from ..clashing_app1.models import NamedURL


@python_2_unicode_compatible
class Copy(NamedURL):
    content = models.TextField()

    def __str__(self):
        return self.content

    class Meta:
        apps = clashing_apps
