# tpm/utils/calculations.py

LOWER_IS_BETTER_KEYWORDS = [
    'breakdown', 'mttr', 'total losses', 'rejection', 'rework',
    'response time', 'repetitive breakdown', 'customer complaint',
    'fatal', 'lti', 'mti', 'near miss', 'accident', 'incident',
    'low illuminated area identified', 'dust level', 'noise level'
]

def compute_achievement(actual: float, target: float, kpi_name: str) -> float:
    """Returns achievement % (can exceed 100 for over-performers)"""
    if actual is None or target is None:
        return 0.0

    lower_is_better = any(
        kw in kpi_name.lower() for kw in LOWER_IS_BETTER_KEYWORDS
    )

    if lower_is_better:
        if target == 0:
            return 100.0 if actual == 0 else 0.0
        return min(100.0, (target / actual) * 100.0) if actual != 0 else 100.0
    else:
        if target == 0:
            return 100.0
        return (actual / target) * 100.0

def compute_oee(availability: float, performance: float, quality: float) -> float:
    """OEE = A x P x Q (inputs as percentages, output as percentage)"""
    if availability is None or performance is None or quality is None:
        return 0.0
    return (availability / 100.0) * (performance / 100.0) * (quality / 100.0) * 100.0

def get_status(achievement: float) -> str:
    """Returns 'on-track' | 'at-risk' | 'behind'"""
    if achievement is None:
        return 'behind'
    if achievement >= 90.0:
        return 'on-track'
    if achievement >= 75.0:
        return 'at-risk'
    return 'behind'

def get_status_css_class(status: str) -> str:
    return {
        'on-track': 'badge-green',
        'at-risk':  'badge-amber',
        'behind':   'badge-red',
    }.get(status, 'badge-muted')
