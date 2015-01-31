from django.apps import apps
from django.db.models import Field
from django.utils import six
from django.utils.functional import cached_property

RECURSIVE_RELATIONSHIP_CONSTANT = 'self'

class RelationalField(Field):

    is_relation = True
    many_to_many = False
    many_to_one = False
    one_to_many = False
    one_to_one = False
    reverse = False

    @cached_property
    def related_model(self):
        # Can't cache this property until all the models are loaded.
        apps.check_models_ready()
        return self.to

    def __init__(self, to, **kwargs):
        super(RelationalField, self)(rel=LegacyRel(self), **kwargs)

        try:
            to._meta
        except AttributeError:
            assert isinstance(to, six.string_types), (
                "%s(%r) is invalid. First parameter to ManyToManyField must be "
                "either a model, a model name, or the string %r" %
                (self.__class__.__name__, to, RECURSIVE_RELATIONSHIP_CONSTANT)
            )

        # Class names must be ASCII in Python 2.x, so we forcibly coerce it
        # here to break early if there's a problem.
        self.to = str(to)

    def db_type(self, connection):
        """
        By default related fields don't have a column as they relate
        to columns of another table.
        """
        return None

    def formfield(self, **kwargs):
        if 'limit_choices_to' not in kwargs:
            kwargs['limit_choices_to'] = self.limit_choices_to

        return super(RelationalField, self).formfield(**kwargs)

    def related_query_name(self):
        """
        This method defines the name that can be used to identify this
        related object in a table-spanning query.
        """
        return self.rel.related_query_name or self.rel.related_name or self.opts.model_name


class LegacyRel(object):

    def __init__(self, field):
        self.field = field

    @property
    def to(self):
        return self.field.to

    @property
    def field_name(self):
        return self.field.field_name

    @property
    def related_name(self):
        return self.field.related_name

    @property
    def related_query_name(self):
        return self.field.related_query_name

    @property
    def limit_choices_to(self):
        return self.field.limit_choices_to

    @property
    def multiple(self):
        return self.field.multiple

    @property
    def parent_link(self):
        return self.field.parent_link

    @property
    def on_delete(self):
        return self.field.on_delete

    @property
    def symmetrical(self):
        return self.field.symmetrical

    def is_hidden(self):
        "Should the related object be hidden?"
        return self.related_name and self.related_name[-1] == '+'

    def get_joining_columns(self):
        return self.field.get_reverse_joining_columns()

    def get_extra_restriction(self, where_class, alias, related_alias):
        return self.field.get_extra_restriction(where_class, related_alias, alias)


    def get_lookup_constraint(self, constraint_class, alias, targets, sources, lookup_type,
                              raw_value):
        return self.field.get_lookup_constraint(constraint_class, alias, targets, sources,
                                                lookup_type, raw_value)
