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

from __future__ import absolute_import, division, print_function

from inspirehep.modules.literaturesuggest.tasks import (
    new_ticket_context,
    reply_ticket_context,
    curation_ticket_context,
    curation_ticket_needed,
    formdata_to_model
)


class StubObj(object):
    def __init__(self, data, extra_data, id=1, id_user=1):
        self.data = data
        self.extra_data = extra_data
        self.id = id
        self.id_user = id_user


class DummyEng(object):
    pass


class StubUser(object):
    def __init__(self, email):
        self.email = email


def test_new_ticket_context():
    data = {
        'titles': [
            {
                'title': 'foo',
            },
        ],
        'external_system_numbers': [
            {
                'value': 'bar',
            },
        ],
    }
    extra_data = {
        'formdata': {
            'extra_comments': [
                'baz',
            ],
            'references': [
                'qux',
            ],
        },
    }

    obj = StubObj(data, extra_data)
    user = StubUser('user@example.com')

    expected = {
        'email': 'user@example.com',
        'title': 'foo',
        'identifier': [
            'bar',
        ],
        'user_comment': [
            'baz',
        ],
        'references': [
            'qux',
        ],
        'object': obj,
        'subject': 'Your suggestion to INSPIRE: foo',
    }
    result = new_ticket_context(user, obj)

    assert expected == result


def test_new_ticket_context_handles_unicode():
    data = {
        'titles': [
            {
                'title': (
                    u'Chocs caractéristiques et ondes simples '
                    u'exceptionnelles pour les systèmes conservatifs à '
                    u"intégrale d'énergie: forme explicite de la solution"
                ),
            },
        ],
    }
    extra_data = {}

    obj = StubObj(data, extra_data)
    user = StubUser('user@example.com')

    expected = {
        'email': 'user@example.com',
        'title': (
            u'Chocs caractéristiques et ondes simples exceptionnelles pour '
            u"les systèmes conservatifs à intégrale d'énergie: forme "
            u'explicite de la solution'
        ),
        'identifier': '',
        'user_comment': '',
        'references': None,
        'object': obj,
        'subject': (
            u'Your suggestion to INSPIRE: Chocs caractéristiques et ondes '
            u'simples exceptionnelles pour les systèmes conservatifs à '
            u"intégrale d'énergie: forme explicite de la solution"
        ),
    }
    result = new_ticket_context(user, obj)

    assert expected == result


def test_reply_ticket_context():
    data = {
        'titles': [
            {
                'title': 'foo',
            },
        ],
    }
    extra_data = {
        'reason': 'bar',
        'url': 'baz',
    }

    obj = StubObj(data, extra_data)
    user = StubUser('user@example.com')

    expected = {
        'object': obj,
        'user': user,
        'title': 'foo',
        'reason': 'bar',
        'record_url': 'baz',
    }
    result = reply_ticket_context(user, obj)

    assert expected == result


def test_curation_ticket_context():
    data = {
        'arxiv_eprints': [
            {
                'value': 'math.GT/0309136',
            },
            {
                'value': '0706.0001v1',
            },
        ],
        'report_numbers': [
            {
                'value': 'foo',
            },
        ],
        'dois': [
            {
                'value': 'bar',
            },
        ],
    }
    extra_data = {
        'recid': 'baz',
        'url': 'qux',
        'formdata': {
            'url': 'quux',
            'references': [
                'plugh',
            ],
            'extra_comments': [
                'xyzzy',
            ]
        }
    }

    obj = StubObj(data, extra_data)
    user = StubUser('user@example.com')

    expected = {
        'recid': 'baz',
        'record_url': 'qux',
        'link_to_pdf': 'quux',
        'email': 'user@example.com',
        'references': [
            'plugh',
        ],
        'user_comment': [
            'xyzzy',
        ],
        'subject': 'math.GT/0309136 arXiv:0706.0001v1 doi:bar foo (#baz)',
    }
    result = curation_ticket_context(user, obj)

    assert expected == result


def test_curation_ticket_needed():
    obj = StubObj({}, {'core': True})
    eng = DummyEng()

    assert curation_ticket_needed(obj, eng)


def test_formdata_to_model_ignores_arxiv_pdf():
    data = {}
    extra_data = {}
    obj = StubObj(data, extra_data)
    formdata = {
        'type_of_doc': 'article',
        'title': 'Test title',
        'url': 'https://arxiv.org/pdf/1511.04200.pdf'
    }

    formdata_to_model(obj, formdata)

    assert 'submission_pdf' not in obj.extra_data


def test_formdata_to_model_ignores_arxiv_additional_url():
    data = {}
    extra_data = {}
    obj = StubObj(data, extra_data)
    formdata = {
        'type_of_doc': 'article',
        'title': 'Test title',
        'additional_url': 'https://arxiv.org/abs/1511.04200'
    }

    record = formdata_to_model(obj, formdata)

    assert 'urls' not in record


def test_formdata_to_model_only_pdf():
    data = {}
    extra_data = {}
    obj = StubObj(data, extra_data)
    formdata = {
        'type_of_doc': 'article',
        'title': 'Test title',
        'url': 'https://ora.ox.ac.uk/content01.pdf'
    }

    formdata_to_model(obj, formdata)

    expected = {
        'submission_pdf': 'https://ora.ox.ac.uk/content01.pdf'
    }

    assert expected == obj.extra_data


def test_formdata_to_model_only_additional_url():
    data = {}
    extra_data = {}
    obj = StubObj(data, extra_data)
    formdata = {
        'type_of_doc': 'article',
        'title': 'Test title',
        'additional_url': 'https://ora.ox.ac.uk/splash_page.html'
    }

    record = formdata_to_model(obj, formdata)

    expected_urls = [{
        'value': 'https://ora.ox.ac.uk/splash_page.html'
    }]

    assert expected_urls == record['urls']
    assert 'submission_pdf' not in obj.extra_data


def test_formdata_to_model_pdf_and_additional_url():
    data = {}
    extra_data = {}
    obj = StubObj(data, extra_data)
    formdata = {
        'type_of_doc': 'article',
        'title': 'Test title',
        'url': 'https://ora.ox.ac.uk/content01.pdf',
        'additional_url': 'https://ora.ox.ac.uk/splash_page.html'
    }

    record = formdata_to_model(obj, formdata)

    expected_extra_data = {
        'submission_pdf': 'https://ora.ox.ac.uk/content01.pdf'
    }

    expected_urls = [{
        'value': 'https://ora.ox.ac.uk/splash_page.html'
    }]

    assert expected_extra_data == obj.extra_data
    assert expected_urls == record['urls']
