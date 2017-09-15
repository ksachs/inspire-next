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

"""Tasks related to record merging."""

from __future__ import absolute_import, division, print_function
from invenio_db import db
from inspirehep.modules.workflows.models import WorkflowsRecordSources


def read_wf_record_source(record_uuid, source):
    entry = WorkflowsRecordSources.query.filter_by(
        record_id=str(record_uuid),
        source=source.lower()
    ).one_or_none()
    return entry


def insert_wf_record_source(json, record_uuid, source):
    """Stores the given json in the WorkflowRecordSource table in the db.
    This object, in the workflow, is known as ``new_root``.

    Important: does not commit the session, in case some other operation
    needs to be done before it

    Args:
        json(dict): the content of the root
        record_uuid(uuid): the record's uuid to associate with the root
        source(string): the source of the root
    """
    record_source = read_wf_record_source(record_uuid=record_uuid, source=source)
    if record_source is None:
        record_source = WorkflowsRecordSources(
            source=source.lower(),
            json=json,
            record_id=record_uuid
        )
        db.session.add(record_source)
    else:
        record_source.json = json


def get_head_source(head_uuid):
    """Return the right source for the record having uuid=``uuid``.

    Args:
        head_uuid(string): the uuid of the record to get the source

    Return:
        (string):
        * ``publisher`` if there is at least a non arxiv root
        * ``arxiv`` if there are no publisher roots and an arxiv root
        * None if there are no root records
    """
    publisher_root = WorkflowsRecordSources.query. \
        filter(WorkflowsRecordSources.record_id == head_uuid). \
        filter(WorkflowsRecordSources.source != 'arxiv'). \
        one_or_none()

    if publisher_root:
        return 'publisher'

    arxiv_root = read_wf_record_source(source='arxiv', record_uuid=head_uuid)
    if arxiv_root:
        return 'arxiv'

    return None
