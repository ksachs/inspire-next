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

from inspire_schemas.api import load_schema, validate
from inspirehep.utils.record import (
    get_abstract,
    get_arxiv_categories,
    get_arxiv_id,
    get_subtitle,
    get_title,
)


def test_get_abstract_returns_first_abstract():
    schema = load_schema('hep')
    subschema = schema['properties']['abstracts']

    record = {
        'abstracts': [
            {
                'source': 'arXiv',
                'value': 'first abstract',
            },
            {
                'source': 'publisher',
                'value': 'second abstract',
            },
        ],
    }

    expected = 'first abstract'
    result = get_abstract(record)

    assert validate(record['abstracts'], subschema) is None
    assert expected == result


def test_get_arxiv_categories_returns_all_arxiv_categories():
    schema = load_schema('hep')
    subschema = schema['properties']['arxiv_eprints']

    record = {
        'arxiv_eprints': [
            {
                'categories': [
                    'nucl-th',
                ],
                'value': '1605.03898'
            },
        ],
    }  # literature/1458300
    assert validate(record['arxiv_eprints'], subschema) is None

    expected = ['nucl-th']
    result = get_arxiv_categories(record)

    assert expected == result


def test_get_arxiv_id_returns_empty_string_when_no_arxiv_eprints():
    record = {}

    expected = ''
    result = get_arxiv_id(record)

    assert expected == result


def test_get_arxiv_id_returns_empty_string_when_arxiv_eprints_is_empty():
    record = {'arxiv_eprints': []}

    expected = ''
    result = get_arxiv_id(record)

    assert expected == result


def test_get_arxiv_id_returns_first_arxiv_identifier():
    record = {
        'arxiv_eprints': [
            {'value': 'first arXiv identifier'},
            {'value': 'second arXiv identifier'},
        ],
    }

    expected = 'first arXiv identifier'
    result = get_arxiv_id(record)

    assert expected == result


def test_get_subtitle_returns_empty_string_when_no_titles():
    record = {}

    expected = ''
    result = get_subtitle(record)

    assert expected == result


def test_get_subtitle_returns_empty_string_when_titles_is_empty():
    record = {'titles': []}

    expected = ''
    result = get_subtitle(record)

    assert expected == result


def test_get_subtitle_returns_first_subtitle():
    record = {
        'titles': [
            {'subtitle': 'first subtitle'},
            {'subtitle': 'second subtitle'},
        ],
    }

    expected = 'first subtitle'
    result = get_subtitle(record)

    assert expected == result


def test_get_title_returns_empty_string_when_no_titles():
    record = {}

    expected = ''
    result = get_title(record)

    assert expected == result


def test_get_title_returns_empty_string_when_titles_is_empty():
    record = {'titles': []}

    expected = ''
    result = get_title(record)

    assert expected == result


def test_get_title_returns_first_title():
    record = {
        'titles': [
            {'title': 'first title'},
            {'title': 'second title'},
        ],
    }

    expected = 'first title'
    result = get_title(record)

    assert expected == result
