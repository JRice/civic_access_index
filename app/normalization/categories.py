AMENITY_CATEGORY_MAP = {
    "supermarket": "grocery",
    "greengrocer": "grocery",
    "pharmacy": "pharmacy",
    "library": "library",
    "clinic": "clinic",
    "hospital": "hospital",
    "school": "school",
    "shelter": "shelter",
}


def normalize_amenity_category(raw_category: str | None) -> str | None:
    if raw_category is None:
        return None
    return AMENITY_CATEGORY_MAP.get(raw_category.lower().strip(), raw_category.lower().strip())

