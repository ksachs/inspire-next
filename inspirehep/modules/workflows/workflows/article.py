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

"""Workflow for processing single arXiv records harvested."""

from __future__ import absolute_import, division, print_function

from workflow.patterns.controlflow import (
    IF,
    IF_ELSE,
)

from inspire_dojson.hep import hep2marc
from inspirehep.modules.workflows.tasks.refextract import extract_journal_info
from inspirehep.modules.workflows.tasks.arxiv import (
    arxiv_author_list,
    arxiv_fulltext_download,
    arxiv_package_download,
    arxiv_plot_extract,
    arxiv_derive_inspire_categories,
)
from inspirehep.modules.workflows.tasks.actions import (
    add_core,
    error_workflow,
    halt_record,
    is_record_relevant,
    is_record_accepted,
    reject_record,
    is_experimental_paper,
    is_marked,
    is_submission,
    is_arxiv_paper,
    mark,
    refextract,
    submission_fulltext_download,
    save_workflow,
)
from inspirehep.modules.workflows.tasks.merging import (
    merge_articles,
    update_record,
    put_new_root_in_extra_data,
    store_root,
)
from inspirehep.modules.workflows.tasks.classifier import (
    classify_paper,
    filter_core_keywords,
)
from inspirehep.modules.workflows.tasks.beard import guess_coreness
from inspirehep.modules.workflows.tasks.magpie import (
    guess_keywords,
    guess_categories,
    guess_experiments,
)
from inspirehep.modules.workflows.tasks.matching import (
    stop_processing,
    pending_in_holding_pen,
    article_exists,
    already_harvested,
    holdingpen_match_with_same_source,
    stop_matched_holdingpen_wf,
    is_matched_wf_previously_rejected,
)
from inspirehep.modules.workflows.tasks.upload import store_record, set_schema
from inspirehep.modules.workflows.tasks.submission import (
    close_ticket,
    create_ticket,
    filter_keywords,
    prepare_keywords,
    remove_references,
    reply_ticket,
    send_robotupload,
    wait_webcoll,
)

from inspirehep.modules.literaturesuggest.tasks import (
    curation_ticket_needed,
    reply_ticket_context,
    new_ticket_context,
    curation_ticket_context,
)


NOTIFY_SUBMISSION = [
    # Special RT integration for submissions
    # ======================================
    create_ticket(
        template="literaturesuggest/tickets/curator_submitted.html",
        queue="HEP_add_user",
        context_factory=new_ticket_context,
        ticket_id_key="ticket_id"
    ),
    reply_ticket(
        template="literaturesuggest/tickets/user_submitted.html",
        context_factory=reply_ticket_context,
        keep_new=True
    ),
]


ADD_INGESTION_MARKS = [
    # Article matching for non-submissions
    # ====================================
    # Query holding pen to see if we already have this article ingested
    #
    # NOTE on updates:
    #     If the same article has been harvested before and the
    #     ingestion has been completed, process is continued
    #     to allow for updates.
    IF(
        is_marked('already-in-holding-pen'),
        [mark('delete', True)]
    ),
    IF(
        is_arxiv_paper,
        [
            # FIXME: This filtering step should be removed when this
            #        workflow includes arXiv CORE harvesting
            IF(
                already_harvested,
                [
                    mark('already-ingested', True),
                    mark('stop', True),
                ]
            ),
        ]
    ),
]


ENHANCE_RECORD = [
    # Article Processing
    # ==================
    IF(
        is_arxiv_paper,
        [
            arxiv_fulltext_download,
            arxiv_package_download,
            arxiv_plot_extract,
            refextract,
            arxiv_derive_inspire_categories,
            arxiv_author_list("authorlist2marcxml.xsl"),
        ]
    ),
    IF(
        is_submission,
        [
            submission_fulltext_download,
            refextract,
        ]
    ),
    extract_journal_info,
    classify_paper(
        taxonomy="HEPont.rdf",
        only_core_tags=False,
        spires=True,
        with_author_keywords=True,
    ),
    filter_core_keywords,
    guess_categories,
    IF(
        is_experimental_paper,
        [guess_experiments]
    ),
    guess_keywords,
    # Predict action for a generic HEP paper based only on title
    # and abstract.
    guess_coreness,  # ("arxiv_skip_astro_title_abstract.pickle)
    # Check if we shall halt or auto-reject
    # =====================================
    put_new_root_in_extra_data,
]


NOTIFY_NOT_ACCEPTED = [
    IF(
        is_submission,
        [reply_ticket(context_factory=reply_ticket_context)]
    )
]


NOTIFY_ALREADY_EXISTING = [
    reject_record('Article was already found on INSPIRE'),
    mark('approved', False),
    reply_ticket(
        template=(
            "literaturesuggest/tickets/"
            "user_rejected_exists.html"
        ),
        context_factory=reply_ticket_context
    ),
    close_ticket(ticket_id_key="ticket_id"),
    mark('stop', True),
    save_workflow,
    stop_processing,
    mark('stop', True)
]


NOTIFY_USER_OR_CURATOR = [
    IF(
        is_submission,
        [
            reply_ticket(
                template='literaturesuggest/tickets/user_accepted.html',
                context_factory=reply_ticket_context,
            ),
        ],
    ),
    IF(
        curation_ticket_needed,
        [
            create_ticket(
                template='literaturesuggest/tickets/curation_core.html',
                queue='HEP_curation',
                context_factory=curation_ticket_context,
                ticket_id_key='curation_ticket_id',
            ),
        ],
    ),
]


POSTENHANCE_RECORD = [
    add_core,
    filter_keywords,
    prepare_keywords,
    remove_references,
]


SEND_TO_LEGACY_AND_WAIT = [
    IF_ELSE(
        is_marked('is-update'),
        [
            send_robotupload(
                marcxml_processor=hep2marc,
                mode="replace",
            ),
        ], [
            send_robotupload(
                marcxml_processor=hep2marc,
                mode="insert"
            ),
            wait_webcoll,
        ]
    ),
]


STOP_IF_EXISTING_SUBMISSION = [
    IF(
        is_submission,
        IF(
            is_marked('is-update'),
            NOTIFY_ALREADY_EXISTING
        )
    )
]


HALT_FOR_APPROVAL = [
    IF_ELSE(
        is_record_relevant,
        [
            halt_record(
                action="hep_approval",
                message="Submission halted for curator approval.",
            )
        ],
        # record not relevant
        [
            reject_record("Article automatically rejected"),
            mark('approved', False),
            save_workflow,
            stop_processing,
        ]
    )
]


STORE_RECORD = [
    store_root,
    store_record
]


CHECK_ALREADY_IN_HOLDINGPEN = [
    IF(
        pending_in_holding_pen,
        mark('already-in-holding-pen', True)
    )
]


ERROR_WITH_UNEXPECTED_WORKFLOW_PATH = [
    mark('unexpected-workflow-path', True),
    error_workflow('Unexpected workflow path.')
]


# Currently we handle harvests as if all were arxiv, that will have to change.
PROCESS_HOLDINGPEN_MATCH_ARXIV = [
    IF(
        holdingpen_match_with_same_source,
        [
            IF_ELSE(
                is_matched_wf_previously_rejected,
                [
                    mark('previously_rejected', True),
                    mark('approved', False),
                    save_workflow,
                    stop_processing,
                ],
                [
                    stop_matched_holdingpen_wf,
                    mark('stopped-matched-holdingpen-wf', True)
                ]
            )
        ],
    )
]


PROCESS_HOLDINGPEN_MATCH_SUBMISSION = [
    IF_ELSE(
        is_matched_wf_previously_rejected,
        [
            mark('previously_rejected', True),
            mark('approved', False),
        ],
        IF_ELSE(
            holdingpen_match_with_same_source,
            # this should have been caught by the form, it's a double
            # submission.
            ERROR_WITH_UNEXPECTED_WORKFLOW_PATH,
            [
                stop_matched_holdingpen_wf,
                mark('stopped-matched-holdingpen-wf', True)
            ],
        )
    )
]


PROCESS_HOLDINGPEN_MATCH = [
    IF(
        is_marked('already-in-holding-pen'),
        IF_ELSE(
            is_submission,
            PROCESS_HOLDINGPEN_MATCH_SUBMISSION,
            IF_ELSE(
                is_arxiv_paper,
                PROCESS_HOLDINGPEN_MATCH_ARXIV,
                # We don't handle yet publisher harvests
                ERROR_WITH_UNEXPECTED_WORKFLOW_PATH,
            ),
        )
    )
]


CHECK_IF_UPDATE = [
    IF(
        article_exists,
        mark('is-update', True),
    )
]


STOP_IF_ALREADY_HARVESTED = [
    IF(
        already_harvested,
        [
            mark('already-ingested', True),
            save_workflow,
            stop_processing
        ]
    )
]


NOTIFY_IF_SUBMISSION = [
    IF(
        is_submission,
        NOTIFY_SUBMISSION,
    )
]


INIT_MARKS = [
    mark('already-ingested', False),
    mark('already-in-holding-pen', False),
    mark('previously_rejected', False),
    mark('is-update', False),
    mark('stopped-matched-holdingpen-wf', False)
]


PRE_PROCESSING = [
    # Make sure schema is set for proper indexing in Holding Pen
    set_schema,
    INIT_MARKS,
]


MERGE_IF_UPDATE = [
    IF(
        is_marked('is-update'),
        [
            merge_articles,
            mark('merged', True)
            # TODO: save record with new non-conflicting merged fields
        ],
    ),
]


STOP_IF_EXISTING_SUBMISSION = [
    IF(
        is_submission,
        IF(
            is_marked('is-update'),
            NOTIFY_ALREADY_EXISTING
        )
    )
]


HALT_FOR_APPROVAL = [
    IF_ELSE(
        is_record_relevant,
        [
            IF_ELSE(
                article_exists,
                halt_record(
                    action="merge_approval",
                    message="Submission halted for curator approval.",
                ),
                halt_record(
                    action="hep_approval",
                    message="Submission halted for curator approval.",
                ),
            )
        ],
        # record not relevant
        [
            reject_record("Article automatically rejected"),
            stop_processing
        ]
    )
]


class Article(object):
    """Article ingestion workflow for Literature collection."""
    name = "HEP"
    data_type = "hep"

    workflow = (
        PRE_PROCESSING +
        [save_workflow] +
        STOP_IF_ALREADY_HARVESTED +
        NOTIFY_IF_SUBMISSION +
        CHECK_ALREADY_IN_HOLDINGPEN +
        PROCESS_HOLDINGPEN_MATCH +
        CHECK_IF_UPDATE +
        ENHANCE_RECORD +
        STOP_IF_EXISTING_SUBMISSION +
        MERGE_IF_UPDATE +
        HALT_FOR_APPROVAL +
        [
            IF_ELSE(
                is_record_accepted,
                (
                    POSTENHANCE_RECORD +
                    STORE_RECORD +
                    SEND_TO_LEGACY_AND_WAIT +
                    NOTIFY_USER_OR_CURATOR
                ),
                NOTIFY_NOT_ACCEPTED,
            ),
            IF(
                is_submission,
                [close_ticket(ticket_id_key="ticket_id")],
            )
        ]
    )
