"""
23. Giving models a custom manager

You can use a custom ``Manager`` in a particular model by extending the base
``Manager`` class and instantiating your custom ``Manager`` in your model.

There are two reasons you might want to customize a ``Manager``: to add extra
``Manager`` methods, and/or to modify the initial ``QuerySet`` the ``Manager``
returns.
"""

from __future__ import unicode_literals

from django.db import models
from django.utils.encoding import python_2_unicode_compatible

# An example of a custom manager called "objects".

class PersonManager(models.Manager):
    def get_fun_people(self):
        return self.filter(fun=True)

    def filter(self, *args, **kwargs):
        print("manager:filter")
        return super(PersonManager, self).filter(*args, **kwargs)

class CustomQuerySet(models.QuerySet):
    def filter(self, *args, **kwargs):
        print("custom:filter")
        return super(CustomQuerySet, self).filter(*args, **kwargs)
    filter.manager = True

    def bar(self, *args, **kwargs):
        print("custom:bar")
        return self.all()
    bar.manager = True

class MyManager(models.Manager):
    def manager_only(self):
        pass

class MyQuerySet(models.QuerySet):
    base_manager_class = MyManager

    def manager_and_queryset_method(self):
        pass

@python_2_unicode_compatible
class Person(models.Model):
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    fun = models.BooleanField()
    objects = PersonManager()
    other_objects = CustomQuerySet.as_manager(base_cls=PersonManager)
    other_other_objects = MyQuerySet.as_manager()

    def __str__(self):
        return "%s %s" % (self.first_name, self.last_name)

# An example of a custom manager that sets get_queryset().

class PublishedBookManager(models.Manager):
    def get_queryset(self):
        return super(PublishedBookManager, self).get_queryset().filter(is_published=True)

@python_2_unicode_compatible
class Book(models.Model):
    title = models.CharField(max_length=50)
    author = models.CharField(max_length=30)
    is_published = models.BooleanField()
    published_objects = PublishedBookManager()
    authors = models.ManyToManyField(Person, related_name='books')

    def __str__(self):
        return self.title

# An example of providing multiple custom managers.

class FastCarManager(models.Manager):
    def get_queryset(self):
        return super(FastCarManager, self).get_queryset().filter(top_speed__gt=150)

@python_2_unicode_compatible
class Car(models.Model):
    name = models.CharField(max_length=10)
    mileage = models.IntegerField()
    top_speed = models.IntegerField(help_text="In miles per hour.")
    cars = models.Manager()
    fast_cars = FastCarManager()

    def __str__(self):
        return self.name
