# -*- coding: utf-8 -*-
#
# This file is part of INSPIRE.
# Copyright (C) 2014-2017 CERN.
#
# INSPIRE is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# INSPIRE is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with INSPIRE. If not, see <http://www.gnu.org/licenses/>.
#
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as an Intergovernmental Organization
# or submit itself to any jurisdiction.

"""Tasks related to manual merge generic record."""

from __future__ import absolute_import, division, print_function

import json

from invenio_db import db

from inspire_json_merger.inspire_json_merger import inspire_json_merge
from inspire_dojson.utils import get_record_ref

from inspirehep.modules.workflows.tasks.merging import (
    insert_wf_record_source,
)
from inspirehep.modules.workflows.utils import with_debug_logging
from inspirehep.utils.record_getter import get_db_record


def _get_head_and_update(obj):
    head = obj.extra_data['head']
    update = obj.extra_data['update']
    return head, update


@with_debug_logging
def merge_records(obj, eng):
    """Merge the records whose ids are defined in the `obj` parameter and store
    the merged record and relative conflicts in `obj.data` and
    `obj.extra_data['conflicts']`.
    """
    head, update = _get_head_and_update(obj)

    merged, conflicts = inspire_json_merge(
        root={},
        head=head,
        update=update,
        head_source=obj.extra_data['head_source']
    )
    obj.data = merged
    obj.extra_data['conflicts'] = [json.loads(c.to_json()) for c in conflicts]


@with_debug_logging
def halt_for_approval(obj, eng):
    """Stop the Workflow engine"""
    eng.halt(
        action="merge_approval",
        msg='Manual Merge halted for curator approval.'
    )


@with_debug_logging
def edit_metadata_and_store(obj, eng):
    """Replace the `head` record with the previously merged record and updates
    some reference in order to delete the `update` record, linking it to the
    new `head`.
    """

    head = get_db_record('lit', obj.extra_data['head_control_number'])
    update = get_db_record('lit', obj.extra_data['update_control_number'])

    head.clear()
    head.update(obj.data)    # head's content will be replaced by merged
    update.merge(head)       # update's uuid will point to head's uuid
    update.delete()          # mark update record as deleted

    # add schema contents to refer deleted record to the merged one
    update['new_record'] = get_record_ref(
        head['control_number'],
        endpoint='record'
    )
    _add_deleted_records(head, update)

    head.commit()
    update.commit()
    db.session.commit()


def _add_deleted_records(new_rec, deleted_rec):
    """Mark `deleted_rec` as replaced by `new_rec` by adding its id to the
    deleted_record list property.
    """
    ref = get_record_ref(deleted_rec['control_number'], 'record')
    new_rec.setdefault('deleted_records', []).append(ref)


def save_records_as_roots(obj, eng):
    """Save `head` and `update` records in the Root table in the db if they
    have different `sources, otherwise only `head` is saved.
    """
    head, update = _get_head_and_update(obj)

    head_source = obj.extra_data['head_source']

    insert_wf_record_source(
        json=head,
        source=head_source,
        record_uuid=obj.extra_data['head_uuid'],
    )

    update_source = obj.extra_data['update_source']

    # need to save just one root per source
    if update_source != head_source:
        insert_wf_record_source(
            json=update,
            source=update_source.lower(),
            record_uuid=obj.extra_data['update_uuid'],
        )
    obj.save()
    db.session.commit()
