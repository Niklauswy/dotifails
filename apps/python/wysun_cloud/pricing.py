"""Approximate on-demand prices (USD/hour) so cards can say «≈ 0,02 $/h».

The table is for us-central1 and is only an orientation; a VM whose type is not listed
shows no price at all.
"""
PRICES = {
    'e2-micro': 0.0084,
    'e2-small': 0.0168,
    'e2-medium': 0.0335,
    'e2-standard-2': 0.067,
    'e2-standard-4': 0.134,
    'e2-standard-8': 0.268,
    'e2-standard-16': 0.536,
    'n2-standard-2': 0.097,
    'n2-standard-4': 0.194,
    'n2-standard-8': 0.388,
    'n1-standard-1': 0.0475,
    'n1-standard-2': 0.095,
    'n1-standard-4': 0.19,
    'g2-standard-4': 0.70,
}

REGION_MULTIPLIERS = (
    ('us-', 1.0),
    ('europe-', 1.1),
    ('southamerica-', 1.5),
    ('asia-', 1.15),
)


def hourly(machine_type, zone):
    """The approximate hourly cost of ``machine_type`` in ``zone``, or None when it is unknown."""
    base = PRICES.get(machine_type)
    if base is None:
        return None
    region = (zone or '').rsplit('-', 1)[0]
    for prefix, multiplier in REGION_MULTIPLIERS:
        if region.startswith(prefix):
            return base * multiplier
    return base
