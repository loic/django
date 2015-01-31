from django.db import transaction, router, connections
from django.db.models import Manager, Q, signals, Model, QuerySet
from django.db.models.relations import RelationalField, RECURSIVE_RELATIONSHIP_CONSTANT


class ManyToManyField(RelationalField):

    many_to_many = True

    def __init__(self, to, symmetrical=None, through=None, through_fields=None,
            db_constraint=True, db_table=None, **kwargs):

        super(ManyToManyField, self).__init__(to, **kwargs)

        if symmetrical is None:
            symmetrical = (to == RECURSIVE_RELATIONSHIP_CONSTANT)
        self.symmetrical = symmetrical

        if through:
            if db_table:
                raise ValueError("Cannot specify a db_table if an intermediary model is used.")
            if not db_constraint:
                raise ValueError("Cannot specify db_constraint=False if a through model is used.")
        elif through_fields:
            raise ValueError("Cannot specify through_fields without a through model.")
        self.through = through
        self.through_fields = through_fields

        self.db_constraint = db_constraint
        self.db_table = db_table

    @property
    def related_fields(self):
        return []


class ReverseManyToManyField(RelationalField):

    many_to_many = True
    reverse = True

    @property
    def related_fields(self):
        return []


class ManyToManyManager(Manager):
    def __init__(self, field=None, instance=None):
        super(ManyToManyManager, self).__init__()

        self.field = field

        self.related_query_name = self.field.related_query_name()

        source_field = self.through._meta.get_field(source_field_name)
        source_related_fields = source_field.related_fields

        self.core_filters = {}
        for lh_field, rh_field in source_related_fields:
            self.core_filters['%s__%s' % (self.related_query_name, rh_field.name)] = getattr(instance, rh_field.attname)

        self.instance = instance
        self.source_field = source_field
        self.target_field = self.through._meta.get_field(target_field_name)
        self.source_field_name = source_field_name
        self.target_field_name = target_field_name
        self.through = field.through
        self.prefetch_cache_name = prefetch_cache_name
        self.related_val = source_field.get_foreign_related_value(instance)
        if None in self.related_val:
            raise ValueError('"%r" needs to have a value for field "%s" before '
                             'this many-to-many relationship can be used.' %
                             (instance, source_field_name))
        # Even if this relation is not to pk, we require still pk value.
        # The wish is that the instance has been already saved to DB,
        # although having a pk value isn't a guarantee of that.
        if instance.pk is None:
            raise ValueError("%r instance needs to have a primary key value before "
                             "a many-to-many relationship can be used." %
                             instance.__class__.__name__)

    def get_queryset(self):
        try:
            return self.instance._prefetched_objects_cache[self.prefetch_cache_name]
        except (AttributeError, KeyError):
            qs = super(ManyToManyManager, self).get_queryset()
            qs._add_hints(instance=self.instance)
            if self._db:
                qs = qs.using(self._db)
            return qs._next_is_sticky().filter(**self.core_filters)

    def get_prefetch_queryset(self, instances, queryset=None):
        if queryset is None:
            queryset = super(ManyToManyManager, self).get_queryset()

        queryset._add_hints(instance=instances[0])
        queryset = queryset.using(queryset._db or self._db)

        query = {'%s__in' % self.related_query_name: instances}
        queryset = queryset._next_is_sticky().filter(**query)

        # M2M: need to annotate the query in order to get the primary model
        # that the secondary model was actually related to. We know that
        # there will already be a join on the join table, so we can just add
        # the select.

        # For non-autocreated 'through' models, can't assume we are
        # dealing with PK values.
        fk = self.through._meta.get_field(self.source_field_name)
        join_table = self.through._meta.db_table
        connection = connections[queryset.db]
        qn = connection.ops.quote_name
        queryset = queryset.extra(select={
            '_prefetch_related_val_%s' % f.attname:
            '%s.%s' % (qn(join_table), qn(f.column)) for f in fk.local_related_fields})
        return (
            queryset,
            lambda result: tuple(
                getattr(result, '_prefetch_related_val_%s' % f.attname)
                for f in fk.local_related_fields
            ),
            lambda inst: tuple(getattr(inst, f.attname) for f in fk.foreign_related_fields),
            False,
            self.prefetch_cache_name,
        )

    def add(self, *objs):
        if not self.through._meta.auto_created:
            opts = self.through._meta
            raise AttributeError(
                "Cannot use add() on a ManyToManyField which specifies an "
                "intermediary model. Use %s.%s's Manager instead." %
                (opts.app_label, opts.object_name)
            )

        db = router.db_for_write(self.through, instance=self.instance)
        with transaction.atomic(using=db, savepoint=False):
            self._add_items(self.source_field_name, self.target_field_name, *objs)

            # If this is a symmetrical m2m relation to self, add the mirror entry in the m2m table
            if self.field.symmetrical:
                self._add_items(self.target_field_name, self.source_field_name, *objs)
    add.alters_data = True

    def remove(self, *objs):
        if not self.through._meta.auto_created:
            opts = self.through._meta
            raise AttributeError(
                "Cannot use remove() on a ManyToManyField which specifies "
                "an intermediary model. Use %s.%s's Manager instead." %
                (opts.app_label, opts.object_name)
            )
        self._remove_items(self.source_field_name, self.target_field_name, *objs)
    remove.alters_data = True

    def clear(self):
        db = router.db_for_write(self.through, instance=self.instance)
        with transaction.atomic(using=db, savepoint=False):
            signals.m2m_changed.send(sender=self.through, action="pre_clear",
                instance=self.instance, reverse=self.field.reverse,
                model=self.model, pk_set=None, using=db)

            filters = self._build_remove_filters(super(ManyToManyManager, self).get_queryset().using(db))
            self.through._default_manager.using(db).filter(filters).delete()

            signals.m2m_changed.send(sender=self.through, action="post_clear",
                instance=self.instance, reverse=self.field.reverse,
                model=self.model, pk_set=None, using=db)
    clear.alters_data = True

    def create(self, **kwargs):
        # This check needs to be done here, since we can't later remove this
        # from the method lookup table, as we do with add and remove.
        if not self.through._meta.auto_created:
            opts = self.through._meta
            raise AttributeError(
                "Cannot use create() on a ManyToManyField which specifies "
                "an intermediary model. Use %s.%s's Manager instead." %
                (opts.app_label, opts.object_name)
            )
        db = router.db_for_write(self.instance.__class__, instance=self.instance)
        new_obj = super(ManyToManyManager, self.db_manager(db)).create(**kwargs)
        self.add(new_obj)
        return new_obj
    create.alters_data = True

    def get_or_create(self, **kwargs):
        db = router.db_for_write(self.instance.__class__, instance=self.instance)
        obj, created = super(ManyToManyManager, self.db_manager(db)).get_or_create(**kwargs)
        # We only need to add() if created because if we got an object back
        # from get() then the relationship already exists.
        if created:
            self.add(obj)
        return obj, created
    get_or_create.alters_data = True

    def update_or_create(self, **kwargs):
        db = router.db_for_write(self.instance.__class__, instance=self.instance)
        obj, created = super(ManyToManyManager, self.db_manager(db)).update_or_create(**kwargs)
        # We only need to add() if created because if we got an object back
        # from get() then the relationship already exists.
        if created:
            self.add(obj)
        return obj, created
    update_or_create.alters_data = True

    def _add_items(self, source_field_name, target_field_name, *objs):
        # source_field_name: the PK fieldname in join table for the source object
        # target_field_name: the PK fieldname in join table for the target object
        # *objs - objects to add. Either object instances, or primary keys of object instances.

        # If there aren't any objects, there is nothing to do.
        if objs:
            new_ids = set()
            for obj in objs:
                if isinstance(obj, self.model):
                    if not router.allow_relation(obj, self.instance):
                        raise ValueError(
                            'Cannot add "%r": instance is on database "%s", value is on database "%s"' %
                            (obj, self.instance._state.db, obj._state.db)
                        )
                    fk_val = self.through._meta.get_field(
                        target_field_name).get_foreign_related_value(obj)[0]
                    if fk_val is None:
                        raise ValueError(
                            'Cannot add "%r": the value for field "%s" is None' %
                            (obj, target_field_name)
                        )
                    new_ids.add(fk_val)
                elif isinstance(obj, Model):
                    raise TypeError(
                        "'%s' instance expected, got %r" %
                        (self.model._meta.object_name, obj)
                    )
                else:
                    new_ids.add(obj)

            db = router.db_for_write(self.through, instance=self.instance)
            vals = (self.through._default_manager.using(db)
                    .values_list(target_field_name, flat=True)
                    .filter(**{
                        source_field_name: self.related_val[0],
                        '%s__in' % target_field_name: new_ids,
                    }))
            new_ids = new_ids - set(vals)

            with transaction.atomic(using=db, savepoint=False):
                if self.field.reverse or source_field_name == self.source_field_name:
                    # Don't send the signal when we are inserting the
                    # duplicate data row for symmetrical reverse entries.
                    signals.m2m_changed.send(sender=self.through, action='pre_add',
                        instance=self.instance, reverse=self.field.reverse,
                        model=self.model, pk_set=new_ids, using=db)

                # Add the ones that aren't there already
                self.through._default_manager.using(db).bulk_create([
                    self.through(**{
                        '%s_id' % source_field_name: self.related_val[0],
                        '%s_id' % target_field_name: obj_id,
                    })
                    for obj_id in new_ids
                ])

                if self.field.reverse or source_field_name == self.source_field_name:
                    # Don't send the signal when we are inserting the
                    # duplicate data row for symmetrical reverse entries.
                    signals.m2m_changed.send(sender=self.through, action='post_add',
                        instance=self.instance, reverse=self.field.reverse,
                        model=self.model, pk_set=new_ids, using=db)

    def _build_remove_filters(self, removed_vals):
        filters = Q(**{self.source_field_name: self.related_val})
        # No need to add a subquery condition if removed_vals is a QuerySet without
        # filters.
        removed_vals_filters = (not isinstance(removed_vals, QuerySet) or
                                removed_vals._has_filters())
        if removed_vals_filters:
            filters &= Q(**{'%s__in' % self.target_field_name: removed_vals})
        if self.field.symmetrical:
            symmetrical_filters = Q(**{self.target_field_name: self.related_val})
            if removed_vals_filters:
                symmetrical_filters &= Q(
                    **{'%s__in' % self.source_field_name: removed_vals})
            filters |= symmetrical_filters
        return filters

    def _remove_items(self, source_field_name, target_field_name, *objs):
        # source_field_name: the PK colname in join table for the source object
        # target_field_name: the PK colname in join table for the target object
        # *objs - objects to remove
        if not objs:
            return

        # Check that all the objects are of the right type
        old_ids = set()
        for obj in objs:
            if isinstance(obj, self.model):
                fk_val = self.target_field.get_foreign_related_value(obj)[0]
                old_ids.add(fk_val)
            else:
                old_ids.add(obj)

        db = router.db_for_write(self.through, instance=self.instance)
        with transaction.atomic(using=db, savepoint=False):
            # Send a signal to the other end if need be.
            signals.m2m_changed.send(sender=self.through, action="pre_remove",
                instance=self.instance, reverse=self.field.reverse,
                model=self.model, pk_set=old_ids, using=db)
            target_model_qs = super(ManyToManyManager, self).get_queryset()
            if target_model_qs._has_filters():
                old_vals = target_model_qs.using(db).filter(**{
                    '%s__in' % self.target_field.related_field.attname: old_ids})
            else:
                old_vals = old_ids
            filters = self._build_remove_filters(old_vals)
            self.through._default_manager.using(db).filter(filters).delete()

            signals.m2m_changed.send(sender=self.through, action="post_remove",
                instance=self.instance, reverse=self.field.reverse,
                model=self.model, pk_set=old_ids, using=db)
