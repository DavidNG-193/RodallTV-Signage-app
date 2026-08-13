from __future__ import annotations

from rodall_signage.ui.responsive import LayoutMetrics


def build_stylesheet(metrics: LayoutMetrics) -> str:
    small_text = max(metrics.body_size - 3, 10)
    badge_text = max(metrics.body_size - 4, 9)

    return f"""
    QMainWindow, QWidget {{
        background: #080807;
        color: #f5f1e8;
        font-family: Arial;
    }}
    QLabel {{
        background: transparent;
    }}

    QFrame#exchangeRateBar {{
        background: #11110f;
        border-bottom: 1px solid #8a6724;
    }}
    QWidget#ratesViewport,
    QWidget#ratesTrack,
    QWidget#ratesGroup,
    QWidget#rateEntry {{
        background: transparent;
    }}
    QLabel#rateSymbol {{
        color: #b9ad96;
        font-size: {max(metrics.body_size - 2, 11)}px;
        letter-spacing: 1px;
    }}
    QLabel#rateValue {{
        color: #fffaf0;
        font-size: {metrics.body_size}px;
        font-weight: 800;
    }}
    QLabel#rateStaticDate {{
        color: #c8b681;
        background: #11110f;
        border-left: 1px solid #8a6724;
        font-size: {max(metrics.body_size - 2, 11)}px;
        padding: 0 12px;
    }}
    QLabel#rateUp {{
        color: #55d68b;
        font-size: {max(metrics.body_size - 2, 11)}px;
        font-weight: 700;
    }}
    QLabel#rateDown {{
        color: #ff6b70;
        font-size: {max(metrics.body_size - 2, 11)}px;
        font-weight: 700;
    }}
    QLabel#rateNeutral {{
        color: #b9b5ad;
        font-size: {max(metrics.body_size - 2, 11)}px;
        font-weight: 700;
    }}
    QLabel#rateStale {{
        color: #e8bd59;
        font-size: {max(metrics.body_size - 2, 11)}px;
        font-weight: 700;
    }}

    QFrame#mediaPanel {{
        background: #030302;
        border: 1px solid #8a6724;
        border-radius: 12px;
    }}

    QFrame#weatherCard {{
        background: qlineargradient(
            x1: 0, y1: 0, x2: 1, y2: 1,
            stop: 0 #258bc2,
            stop: 0.55 #1672aa,
            stop: 1 #0d5286
        );
        border: 1px solid #2b8ec2;
        border-radius: 18px;
    }}
    QLabel#weatherLocation {{
        color: #eef8ff;
        font-size: {metrics.title_size}px;
        font-weight: 800;
    }}
    QLabel#weatherIcon {{
        color: #ffc43d;
        font-size: {max(metrics.value_size - 4, 36)}px;
    }}
    QLabel#weatherValue {{
        color: #ffffff;
        font-size: {metrics.value_size + 8}px;
        font-weight: 900;
    }}
    QLabel#weatherCondition {{
        color: #ffffff;
        font-size: {metrics.body_size + 3}px;
        font-weight: 500;
    }}
    QLabel#weatherApparent {{
        color: #d8f1ff;
        font-size: {small_text}px;
        font-weight: 600;
    }}
    QFrame#weatherDivider {{
        color: rgba(255, 255, 255, 70);
        background: rgba(255, 255, 255, 70);
        border: none;
        max-height: 1px;
    }}
    QLabel#weatherDetail {{
        color: #d8f1ff;
        font-size: {small_text + 1}px;
        font-weight: 600;
    }}
    QLabel#weatherDetailStrong {{
        color: #ffffff;
        font-size: {small_text + 1}px;
        font-weight: 800;
    }}
    QLabel#weatherAvailability {{
        color: #f6c85f;
        font-size: {badge_text}px;
        font-weight: 700;
    }}

    QFrame#referencesPanel {{
        background: #11110f;
        border: 1px solid #a37a2d;
        border-radius: 16px;
    }}
    QLabel#cardTitle {{
        color: #f0cf70;
        font-size: {max(metrics.title_size - 1, 12)}px;
        font-weight: 800;
        letter-spacing: 0px;
    }}
    QLabel#referencesCount {{
        color: #a99e8b;
        font-size: {small_text}px;
    }}
    QLabel#referencesAvailability {{
        color: #e8bd59;
        font-size: {badge_text}px;
        font-weight: 700;
    }}
    QFrame#referenceItem {{
        background: #181714;
        border: 1px solid #514323;
        border-radius: 11px;
    }}
    QLabel#referenceCodeBadge {{
        color: #e0c979;
        background: #0d0d0b;
        border: 1px solid #685326;
        border-radius: 5px;
        padding: 3px 5px;
        font-size: {max(badge_text - 2, 9)}px;
        font-family: "DejaVu Sans Mono", "Liberation Mono", Consolas, monospace;
    }}
    QLabel#referenceTitle {{
        color: #fffaf0;
        font-size: {max(metrics.body_size - 2, 11)}px;
        font-weight: 800;
    }}
    QLabel#referenceLocation {{
        color: #b7ad9b;
        font-size: {badge_text}px;
    }}
    QLabel#operationImport {{
        color: #f1c75b;
        background: #352b17;
        border-radius: 8px;
        padding: 2px 7px;
        font-size: {badge_text}px;
        font-weight: 800;
    }}
    QLabel#operationExport {{
        color: #d8dde2;
        background: #292b2d;
        border-radius: 8px;
        padding: 2px 7px;
        font-size: {badge_text}px;
        font-weight: 800;
    }}
    QLabel#statusPositive {{
        color: #61e295;
        background: #123421;
        border: 1px solid #276a43;
        border-radius: 8px;
        padding: 2px 7px;
        font-size: {badge_text}px;
        font-weight: 800;
    }}
    QLabel#statusNegative {{
        color: #ff767b;
        background: #3b1719;
        border: 1px solid #762e32;
        border-radius: 8px;
        padding: 2px 7px;
        font-size: {badge_text}px;
        font-weight: 800;
    }}
    QLabel#statusNeutral {{
        color: #d6d2ca;
        background: #2a2926;
        border: 1px solid #54514b;
        border-radius: 8px;
        padding: 2px 7px;
        font-size: {badge_text}px;
        font-weight: 800;
    }}
    QLabel#emptyState {{
        color: #a59b89;
        font-size: {metrics.body_size}px;
    }}

    QLabel#applicationStatusBar {{
        background: #11110f;
        color: #b7ad9b;
        border-top: 1px solid #8a6724;
        padding-left: 14px;
        font-size: {small_text}px;
    }}
    QMainWindow[appState="Degraded"] QLabel#applicationStatusBar {{
        color: #e8bd59;
    }}

    QScrollArea,
    QWidget#referencesViewport,
    QScrollArea > QWidget > QWidget {{
        background: transparent;
        border: none;
    }}
    """
