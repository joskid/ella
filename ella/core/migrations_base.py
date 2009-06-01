
from south.db import db
from django.db import models
from django.utils.datastructures import SortedDict
from django.conf import settings

from ella.core.models import *


def alter_foreignkey_to_int(table, field):
    '''
    real alter foreignkeyField to integerField
    with all constraint deletion
    '''
    fk_field = '%s_id' % field
    db.alter_column(table, fk_field, models.IntegerField())
    db.rename_column(table, fk_field, field)
    db.add_column(table, fk_field, models.IntegerField())
    db.delete_column(table, fk_field)
    db.delete_index(table, [fk_field])

def migrate_foreignkey(app_label, model, table, field, orm):
    s = {
        'app_label': app_label,
        'model': model,
        'table': table,
        'field': field,
        'fk_field': '%s_id' % field,
    }
    db.execute('''
        UPDATE
            `%(table)s` tbl INNER JOIN `core_publishable` pub ON (tbl.`id` = pub.`old_id`)
        SET
            tbl.`%(field)s` = pub.`id`
        WHERE
            pub.`content_type_id` = (SELECT ct.`id` FROM `django_content_type` ct WHERE ct.`app_label` = '%(app_label)s' AND ct.`model` = '%(model)s');
        ''' % s
    )
    db.rename_column(s['table'], s['field'], s['fk_field'])
    db.alter_column(s['table'], s['fk_field'], models.ForeignKey(orm['%(app_label)s.%(model)s' % s]))


class BasePublishableDataMigration(object):

    app_label = ''
    model = ''
    table = '%s_%s' % (app_label, model)

    publishable_uncommon_cols = {}

    def alter_self_foreignkeys(self, orm):
        '''
        alter and migrate all tables that has foreign keys to this model
        '''
        # drop foreign key constraint from intermediate table
        alter_foreignkey_to_int('%s_authors' % self.table, self.model)

    def move_self_foreignkeys(self, orm):
        '''
        alter all data from tables that has foreign keys to this model
        '''
        # update authors
        db.execute('''
            INSERT INTO
                `core_publishable_authors` (`publishable_id`, `author_id`)
            SELECT
                art.`publishable_ptr_id`, art_aut.`author_id`
            FROM
                `%(table)s` art INNER JOIN `%(table)s_authors` art_aut ON (art.`id` = art_aut.`%(model)s`);
            ''' % self.substitute
        )
        db.delete_table('%s_authors' % self.table)


    depends_on = (
        ("core", "0002_publishable_models"),
    )

    @property
    def publishable_cols(self):
        c = {
            'title': 'title',
            'slug': 'slug',
            'category_id': 'category_id',
            'photo_id': 'photo_id',
        }
        c.update(self.publishable_uncommon_cols)
        return SortedDict(c)

    @property
    def generic_relations(self):
        # TODO find better way then this hardcoded...
        keys = ('table', 'ct_id', 'obj_id')
        gens = []
        if 'tagging' in settings.INSTALLED_APPS:
            gens.append(('tagging_taggeditem', 'content_type_id', 'object_id'))
        if 'ella.comments' in settings.INSTALLED_APPS:
            gens.append(('comments_comment', 'target_ct_id', 'target_id'))
        return [dict(zip(keys, v)) for v in gens]

    @property
    def substitute(self):
        return {
            'app_label': self.app_label,
            'model': self.model,
            'table': self.table,
            'cols_to': ', '.join(self.publishable_cols.keys()),
            'cols_from': ', '.join(self.publishable_cols.values()),
        }


    def forwards(self, orm):
        # add a temporary column on core_publishable to remember the old ID
        db.add_column('core_publishable', 'old_id', models.IntegerField(null=True))

        # migrate publishables
        self.forwards_publishable(orm)

        # migrate generic relations
        self.forwards_generic_relations(orm)

        # migrate placements
        #self.forwards_placements(orm)

        # migrate related
        #self.forwards_related(orm)

        # delete temporary column to remember the old ID
        db.delete_column('core_publishable', 'old_id')

    def forwards_publishable(self, orm):
        '''
        creation of publishable objects

        TODO: sync publish_from
        '''

        # move the data
        db.execute('''
            INSERT INTO
                `core_publishable` (old_id, content_type_id, %(cols_to)s)
            SELECT
                a.id, ct.id, %(cols_from)s
            FROM
                `%(table)s` a, `django_content_type` ct
            WHERE
                ct.`app_label` = '%(app_label)s' AND  ct.`model` = '%(model)s';
            ''' % self.substitute
        )

        # add link to parent
        db.add_column(self.table, 'publishable_ptr', models.IntegerField(null=True, blank=True))

        # update the link
        db.execute('''
            UPDATE
                `core_publishable` pub INNER JOIN `%(table)s` art ON (art.`id` = pub.`old_id`)
            SET
                art.`publishable_ptr` = pub.`id`
            WHERE
                pub.`content_type_id` = (SELECT ct.`id` FROM `django_content_type` ct WHERE ct.`app_label` = '%(app_label)s' AND ct.`model` = '%(model)s');
            ''' % self.substitute
        )

        # remove constraints from all models reffering to us
        self.alter_self_foreignkeys(orm)

        # drop primary key
        db.alter_column(self.table, 'id', models.IntegerField())
        db.drop_primary_key(self.table)

        # replace it with a link to parent
        db.rename_column(self.table, 'publishable_ptr', 'publishable_ptr_id')
        db.alter_column(self.table, 'publishable_ptr_id', models.OneToOneField(orm['core.Publishable'], null=False, blank=False))

        # move data, that were pointing to us
        self.move_self_foreignkeys(orm)

        # drop duplicate columns
        for column in self.publishable_cols.values():
            db.delete_column(self.table, column)

    def forwards_generic_relations(self, orm):
        '''
        Updates all generic relations
        '''
        for gen in self.generic_relations:
            sub = dict.copy(self.substitute)
            sub.update(gen)
            db.execute('''
                UPDATE
                    `%(table)s` gen INNER JOIN `core_publishable` pub ON (gen.`%(ct_id)s` = pub.`content_type_id` AND gen.`%(obj_id)s` = pub.`old_id`)
                SET
                    gen.`%(obj_id)s` = pub.`id`
                WHERE
                    pub.`content_type_id` = (SELECT ct.`id` FROM `django_content_type` ct WHERE ct.`app_label` = '%(app_label)s' AND  ct.`model` = '%(model)s');
            ''' % sub)

    def forwards_placements(self, orm):
        '''
        TODO: dodelat
        '''

        app = self.app_name
        mod = self.module_name
        table = '%s_%s' % (app, mod)

        db.add_column('core_placement', 'publishable_id', models.IntegerField(null=True))

        # MIGRATE PLACEMENTS
        db.execute('''
                UPDATE
                    `core_placement` plac INNER JOIN `core_publishable` pub ON (plac.`target_ct_id` = pub.`content_type_id` AND plac.`target_id` = pub.`old_id`)
                SET
                    plac.`publishable_id` = pub.`id`
                WHERE
                    pub.`content_type_id` = (SELECT ct.`id` FROM `django_content_type` ct WHERE ct.`app_label` = '%(app)s' AND  ct.`model` = '%(mod)s');
            ''' % {'app': app, 'mod': mod, 'table': table}
        )

        db.alter_column('core_placement', 'publishable_id', models.ForeignKey(Publishable))

        # TODO: move it via south
        db.execute('''
                ALTER TABLE `core_placement` DROP FOREIGN KEY `core_placement_ibfk_2`;
        ''')

        db.create_index('core_placement', ['publishable_id'])
        db.delete_column('core_placement', 'target_ct_id')
        db.delete_column('core_placement', 'target_id')

    def forwards_related(self, orm):
        pass

    def backwards(self, orm):
        "Write your backwards migration here"
        print 'there is no way back'


    # this is taken directly from the class by south, so it must be simple property,
    # but there will be added some more freezes in children of this class
    models = {
        'core.publishable': {
            'Meta': {'app_label': "'core'"},
            '_stub': True,
            'id': ('models.AutoField', [], {'primary_key': 'True'})
        },
    }


    complete_apps = []

