from django.db.models import CASCADE
from django.db.models.relations import RelationalField


class ForeignKey(RelationalField):

    many_to_one = True

    def __init__(self, to, to_field=None, related_name=None, related_query_name=None,
            limit_choices_to=None, on_delete=CASCADE, db_constraint=True, **kwargs):

        self.to = to
        self.related_name = related_name
        self.related_query_name = related_query_name
        self.limit_choices_to = limit_choices_to
        self.on_delete = on_delete
        self.db_contraint = db_constraint

        super(ForeignKey, self).__init__(**kwargs)


class ReverseForeignKey(RelationalField):

    one_to_many = True

