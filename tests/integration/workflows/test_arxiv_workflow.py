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

"""Tests for arXiv workflows."""

from __future__ import absolute_import, division, print_function

import json
import mock
import os
import StringIO

from invenio_search import current_search_client as es
from invenio_db import db
from invenio_records.models import RecordMetadata
from invenio_workflows import (
    ObjectStatus,
    WorkflowEngine,
    start,
    workflow_object_class,
)

from calls import (
    already_harvested_on_legacy_record,
    do_accept_core,
    do_webcoll_callback,
    do_robotupload_callback,
    do_resolve_conflicts,
    generate_record,
)
from mocks import (
    fake_download_file,
    fake_beard_api_request,
    fake_magpie_api_request,
)
from utils import get_halted_workflow
from inspirehep.modules.workflows.tasks.merging import (
    insert_wf_record_source,
    _get_match_recid
)
from inspirehep.modules.migrator.tasks import record_insert_or_replace


def load_json_fixture(test_dir, file_name):
    base_dir = os.path.dirname(os.path.realpath(__file__))
    with open(os.path.join(base_dir, test_dir, file_name)) as f:
        return json.loads(f.read())


@mock.patch(
    'inspirehep.modules.workflows.tasks.arxiv.is_pdf_link'
)
def run_workflow(mock_is_pdf_link, app, record, extra_config=None):
    extra_config = extra_config or {}
    with mock.patch.dict(app.config, extra_config):
        workflow_uuid = start('article', [record])

    eng = WorkflowEngine.from_uuid(workflow_uuid)
    obj = eng.processed_objects[0]

    return obj.id


@mock.patch(
    'inspirehep.modules.workflows.tasks.arxiv.download_file_to_workflow',
    side_effect=fake_download_file,
)
@mock.patch(
    'inspirehep.modules.workflows.tasks.beard.json_api_request',
    side_effect=fake_beard_api_request,
)
@mock.patch(
    'inspirehep.modules.workflows.tasks.magpie.json_api_request',
    side_effect=fake_magpie_api_request,
)
@mock.patch(
    'inspirehep.modules.workflows.tasks.refextract.extract_references_from_file',
    return_value=[],
)
def test_harvesting_arxiv_workflow_manual_rejected(
    mocked_arxiv_download,
    mocked_api_request_beard,
    mocked_api_request_magpie,
    mocked_refextract_extract_refs,
    workflow_app,
    mocked_external_services,
):
    """Test a full harvesting workflow."""

    record = generate_record()
    extra_config = {
        "BEARD_API_URL": "http://example.com/beard",
        "MAGPIE_API_URL": "http://example.com/magpie",
    }

    workflow_uuid, eng, obj = get_halted_workflow(
        app=workflow_app,
        extra_config=extra_config,
        record=record,
    )

    obj.remove_action()
    obj.extra_data["approved"] = False
    obj.save()

    db.session.commit()

    eng = WorkflowEngine.from_uuid(workflow_uuid)
    obj = eng.processed_objects[0]
    obj_id = obj.id
    obj.continue_workflow()
    obj = workflow_object_class.get(obj_id)
    # It was rejected
    assert obj.status == ObjectStatus.COMPLETED


@mock.patch(
    'inspirehep.modules.workflows.tasks.arxiv.download_file_to_workflow',
    side_effect=fake_download_file,
)
@mock.patch(
    'inspirehep.modules.workflows.tasks.arxiv.is_pdf_link',
    return_value=True
)
@mock.patch(
    'inspirehep.modules.workflows.tasks.beard.json_api_request',
    side_effect=fake_beard_api_request,
)
@mock.patch(
    'inspirehep.modules.workflows.tasks.magpie.json_api_request',
    side_effect=fake_magpie_api_request,
)
@mock.patch(
    'inspirehep.modules.workflows.tasks.refextract.extract_references_from_file',
    return_value=[],
)
def test_harvesting_arxiv_workflow_already_on_legacy(
    mocked_download,
    mocked_is_pdf,
    mocked_api_request_beard,
    mocked_api_request_magpie,
    mocked_refextract_extract_refs,
    workflow_app,
    mocked_external_services
):
    """Test a full harvesting workflow."""
    record, categories = already_harvested_on_legacy_record()

    extra_config = {
        "BEARD_API_URL": "http://example.com/beard",
        "MAGPIE_API_URL": "http://example.com/magpie",
        'ARXIV_CATEGORIES_ALREADY_HARVESTED_ON_LEGACY': categories,
    }
    with workflow_app.app_context():
        with mock.patch.dict(workflow_app.config, extra_config):
            workflow_uuid = start('article', [record])

        eng = WorkflowEngine.from_uuid(workflow_uuid)
        obj = eng.processed_objects[0]

        assert obj.status == ObjectStatus.COMPLETED
        assert 'already-ingested' in obj.extra_data
        assert obj.extra_data['already-ingested']


@mock.patch(
    'inspirehep.modules.workflows.tasks.arxiv.download_file_to_workflow',
    side_effect=fake_download_file,
)
@mock.patch(
    'inspirehep.modules.workflows.utils.download_file_to_workflow',
    side_effect=fake_download_file,
)
@mock.patch(
    'inspirehep.modules.workflows.tasks.beard.json_api_request',
    side_effect=fake_beard_api_request,
)
@mock.patch(
    'inspirehep.modules.workflows.tasks.magpie.json_api_request',
    side_effect=fake_magpie_api_request,
)
@mock.patch(
    'inspirehep.modules.workflows.tasks.matching.match',
    return_value=iter([]),
)
@mock.patch(
    'inspirehep.modules.workflows.tasks.refextract.extract_references_from_file',
    return_value=[],
)
def test_harvesting_arxiv_workflow_manual_accepted(
    mocked_refextract_extract_refs,
    mocked_matching_match,
    mocked_api_request_magpie,
    mocked_api_request_beard,
    mocked_download_utils,
    mocked_download_arxiv,
    workflow_app,
    mocked_external_services,
):
    record = generate_record()
    """Test a full harvesting workflow."""

    workflow_uuid, eng, obj = get_halted_workflow(
        app=workflow_app,
        record=record,
    )

    do_accept_core(
        app=workflow_app,
        workflow_id=obj.id,
    )

    eng = WorkflowEngine.from_uuid(workflow_uuid)
    obj = eng.processed_objects[0]
    assert obj.status == ObjectStatus.WAITING

    response = do_robotupload_callback(
        app=workflow_app,
        workflow_id=obj.id,
        recids=[12345],
    )
    assert response.status_code == 200

    obj = workflow_object_class.get(obj.id)
    assert obj.status == ObjectStatus.WAITING

    response = do_webcoll_callback(app=workflow_app, recids=[12345])
    assert response.status_code == 200

    eng = WorkflowEngine.from_uuid(workflow_uuid)
    obj = eng.processed_objects[0]
    # It was accepted
    assert obj.status == ObjectStatus.COMPLETED


@mock.patch(
    'inspirehep.modules.workflows.tasks.arxiv.is_pdf_link',
    return_value=True
)
@mock.patch(
    'inspirehep.modules.workflows.tasks.arxiv.download_file_to_workflow',
    side_effect=fake_download_file,
)
@mock.patch(
    'inspirehep.modules.workflows.tasks.beard.json_api_request',
    side_effect=fake_beard_api_request,
)
@mock.patch(
    'inspirehep.modules.workflows.tasks.magpie.json_api_request',
    side_effect=fake_magpie_api_request,
)
def test_match_in_holdingpen_stops_pending_wf(
    mocked_api_request_magpie,
    mocked_api_request_beard,
    mocked_download_arxiv,
    mocked_is_pdf,
    workflow_app,
    mocked_external_services,
):
    record = generate_record()

    eng_uuid = start('article', [record])
    es.indices.refresh('holdingpen-hep')
    eng = WorkflowEngine.from_uuid(eng_uuid)
    old_wf = eng.objects[0]
    obj_id = old_wf.id

    assert old_wf.status == ObjectStatus.HALTED
    assert old_wf.extra_data['previously_rejected'] is False

    record2 = record
    record['titles'][0]['title'] = 'This is an update that will match the wf in the holdingpen'
    eng_uuid2 = start('article', [record2])
    es.indices.refresh('holdingpen-hep')
    eng2 = WorkflowEngine.from_uuid(eng_uuid2)
    update_wf = eng2.objects[0]

    assert update_wf.status == ObjectStatus.HALTED
    assert update_wf.extra_data['already-ingested'] is False
    assert update_wf.extra_data['already-in-holding-pen'] is True
    assert update_wf.extra_data['previously_rejected'] is False
    assert update_wf.extra_data['stopped-matched-holdingpen-wf'] is True
    assert update_wf.extra_data['is-update'] is False

    old_wf = workflow_object_class.get(obj_id)
    assert old_wf.extra_data['already-ingested'] is False
    assert old_wf.extra_data['already-in-holding-pen'] is False
    assert old_wf.extra_data['previously_rejected'] is False
    assert old_wf.extra_data['stopped-by-wf'] == str(update_wf.id)
    assert old_wf.extra_data.get('approved') is None
    assert old_wf.extra_data['is-update'] is False
    assert old_wf.status == ObjectStatus.COMPLETED


@mock.patch(
    'inspirehep.modules.workflows.tasks.arxiv.is_pdf_link',
    return_value=True
)
@mock.patch(
    'inspirehep.modules.workflows.tasks.arxiv.download_file_to_workflow',
    side_effect=fake_download_file,
)
@mock.patch(
    'inspirehep.modules.workflows.tasks.beard.json_api_request',
    side_effect=fake_beard_api_request,
)
@mock.patch(
    'inspirehep.modules.workflows.tasks.magpie.json_api_request',
    side_effect=fake_magpie_api_request,
)
def test_match_in_holdingpen_previously_rejected_wf_stop(
    mocked_api_request_magpie,
    mocked_api_request_beard,
    mocked_download_arxiv,
    mocked_is_pdf,
    workflow_app,
    mocked_external_services,
):
    record = generate_record()

    eng_uuid = start('article', [record])
    es.indices.refresh('holdingpen-hep')
    eng = WorkflowEngine.from_uuid(eng_uuid)
    obj_id = eng.objects[0].id
    obj = workflow_object_class.get(obj_id)
    obj.extra_data["approved"] = False
    obj.continue_workflow()
    obj = workflow_object_class.get(obj_id)
    assert obj.status == ObjectStatus.COMPLETED
    assert obj.extra_data.get('approved') is False
    # generated rejected wf

    record['titles'][0]['title'] = 'This is an update that will match the wf in the holdingpen'
    # this workflow matches in the holdingpen and stops because the
    # matched one was rejected
    eng_uuid = start('article', [record])
    eng = WorkflowEngine.from_uuid(eng_uuid)
    obj_id = eng.objects[0].id
    obj = workflow_object_class.get(obj_id)

    assert obj.status == ObjectStatus.COMPLETED
    assert obj.extra_data['already-in-holding-pen'] is True
    assert obj.extra_data['previously_rejected'] is True


@mock.patch(
    'inspirehep.modules.workflows.tasks.arxiv.is_pdf_link',
    return_value=True
)
@mock.patch(
    'inspirehep.modules.workflows.tasks.arxiv.download_file_to_workflow',
    side_effect=fake_download_file,
)
@mock.patch(
    'inspirehep.modules.workflows.tasks.beard.json_api_request',
    side_effect=fake_beard_api_request,
)
@mock.patch(
    'inspirehep.modules.workflows.tasks.magpie.json_api_request',
    side_effect=fake_magpie_api_request,
)
def test_match_in_holdingpen_different_sources_continues(
    mocked_api_request_magpie,
    mocked_api_request_beard,
    mocked_download_arxiv,
    mocked_is_pdf,
    workflow_app,
    mocked_external_services,
):
    record = generate_record()

    eng_uuid = start('article', [record])
    es.indices.refresh('holdingpen-hep')
    eng = WorkflowEngine.from_uuid(eng_uuid)
    obj_id = eng.objects[0].id
    obj = workflow_object_class.get(obj_id)
    assert obj.status == ObjectStatus.HALTED
    # generated wf pending in holdingpen

    record['titles'][0]['title'] = 'This is an update that will match the wf in the holdingpen'
    record['acquisition_source']['source'] = 'but not the source'
    # this workflow matches in the holdingpen but continues because has a
    # different source
    eng_uuid = start('article', [record])
    eng = WorkflowEngine.from_uuid(eng_uuid)
    obj_id = eng.objects[0].id
    obj = workflow_object_class.get(obj_id)

    assert obj.extra_data['already-in-holding-pen'] is True
    assert obj.extra_data['stopped-matched-holdingpen-wf'] is False
    assert obj.extra_data['previously_rejected'] is False


@mock.patch(
    'inspirehep.modules.workflows.tasks.arxiv.is_pdf_link',
    return_value=True
)
@mock.patch(
    'inspirehep.modules.workflows.tasks.arxiv.download_file_to_workflow',
    side_effect=fake_download_file,
)
@mock.patch(
    'inspirehep.modules.workflows.tasks.beard.json_api_request',
    side_effect=fake_beard_api_request,
)
@mock.patch(
    'inspirehep.modules.workflows.tasks.magpie.json_api_request',
    side_effect=fake_magpie_api_request,
)
def test_merge_with_already_existing_article_in_the_db(
    mocked_api_request_magpie,
    mocked_api_request_beard,
    mocked_download_arxiv,
    mocked_is_pdf,
    workflow_app,
    mocked_external_services,
):
    head = record_insert_or_replace(load_json_fixture('fixtures', 'merger_head.json'))
    db.session.commit()
    es.indices.refresh('records-hep')

    insert_wf_record_source(
        record_uuid=head.id,
        source='arXiv',
        json=load_json_fixture('fixtures', 'merger_root.json'),
    )
    es.indices.refresh('records-hep')
    update = load_json_fixture('fixtures', 'merger_update.json')

    obj_id = run_workflow(
        app=workflow_app,
        extra_config={
            'ARXIV_CATEGORIES_ALREADY_HARVESTED_ON_LEGACY': [],
            'PRODUCTION_MODE': False,
        },
        record=update,
    )

    do_resolve_conflicts(workflow_app, obj_id)

    obj = workflow_object_class.get(obj_id)

    response = do_robotupload_callback(
        app=workflow_app,
        workflow_id=obj_id,
        recids=[_get_match_recid(obj)],
    )

    assert response.status_code == 200
    assert obj.status == ObjectStatus.COMPLETED
    assert obj.extra_data['is-update'] is True
    assert obj.extra_data['merged'] is True


@mock.patch(
    'inspirehep.modules.records.api.open_url_or_path',
    return_value=StringIO.StringIO()
)
@mock.patch(
    'inspirehep.modules.workflows.tasks.arxiv.download_file_to_workflow',
    side_effect=fake_download_file,
)
@mock.patch(
    'inspirehep.modules.workflows.tasks.beard.json_api_request',
    side_effect=fake_beard_api_request,
)
@mock.patch(
    'inspirehep.modules.workflows.tasks.magpie.json_api_request',
    side_effect=fake_magpie_api_request,
)
def test_merge_without_conflicts_does_not_halt(
    mocked_api_request_magpie,
    mocked_api_request_beard,
    mocked_download_arxiv,
    mocked_is_pdf,
    workflow_app,
    mocked_external_services,
):
    head = record_insert_or_replace(load_json_fixture('fixtures', 'merger_head.json'))
    es.indices.refresh('records-hep')

    head = RecordMetadata.query.filter(RecordMetadata.id == head.id).one()
    update = head.json
    update['titles'][0]['title'] = 'Foo Bar title'

    # this function starts the workflow
    obj_id = run_workflow(
        app=workflow_app,
        extra_config={
            'ARXIV_CATEGORIES_ALREADY_HARVESTED_ON_LEGACY': [],
            'PRODUCTION_MODE': False,
        },
        record=update,
    )

    obj = workflow_object_class.get(obj_id)

    assert obj.extra_data['is-update'] is True
    assert obj.extra_data['merged'] is True
    assert obj.extra_data.get('conflicts') == []
    assert obj.status == ObjectStatus.COMPLETED
