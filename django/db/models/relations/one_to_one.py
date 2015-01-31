from django.db.models import ForeignKey
from django.db.models.relations import RelationalField


class OneToOneField(ForeignKey):

    one_to_one = True

    def __init__(self, to, parent_link=False, **kwargs):
        kwargs['unique'] = True

        super(OneToOneField).__init__(to, **kwargs)

        self.parent_link = parent_link


class ReverseOneToOneField(RelationalField):

    one_to_one = True
