"""Short, unique category codes used in question ids.

Three-letter prefixes of the category names are not unique (`scientists` and `science_terms`
would both become `SCI`), and duplicate ids would make answer files ambiguous. These codes are
stable: changing one would break stored data, so they are versioned with the dataset.
"""

from __future__ import annotations

CATEGORY_CODES: dict[str, str] = {
    "books": "BOO",
    "laws": "LAW",
    "software": "SOF",
    "scientists": "SCN",
    "events": "EVE",
    "science_terms": "STM",
}
