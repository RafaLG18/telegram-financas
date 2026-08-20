"""Business rules.

This package does NOT know that Telegram exists. It is the boundary that lets
the rules be tested without starting a bot and, later on, lets another interface
(web, CLI, export) be plugged in.

Split by domain: `categories`, `transactions`, `reports` and `drafts`. The public
API is re-exported here, so `from ..core import summary` keeps working -
importing from the specific module is optional, not mandatory.
"""

from __future__ import annotations

from .categories import (
    DEFAULT_CATEGORIES,
    find_category_by_name,
    list_categories,
    seed_categories,
)
from .drafts import (
    active_draft,
    clear_chat_drafts,
    discard_draft,
    finish_draft,
    get_draft,
    new_draft,
    purge_old_drafts,
)
from .reports import CategoryLine, Summary, month_range, summary
from .transactions import (
    InvalidAmountError,
    RemovedTransaction,
    delete_transaction,
    last_transaction,
    record_transaction,
    undo_last,
)

__all__ = [
    "DEFAULT_CATEGORIES",
    "CategoryLine",
    "InvalidAmountError",
    "RemovedTransaction",
    "Summary",
    "active_draft",
    "clear_chat_drafts",
    "delete_transaction",
    "discard_draft",
    "find_category_by_name",
    "finish_draft",
    "get_draft",
    "last_transaction",
    "list_categories",
    "month_range",
    "new_draft",
    "purge_old_drafts",
    "record_transaction",
    "seed_categories",
    "summary",
    "undo_last",
]
