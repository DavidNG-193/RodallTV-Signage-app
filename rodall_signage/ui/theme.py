from __future__ import annotations

from rodall_signage.ui.responsive import LayoutMetrics


def build_stylesheet(metrics: LayoutMetrics) -> str:
    small_text = max(metrics.body_size - 3, 10)
    badge_text = max(metrics.body_size - 4, 9)

    return f"""
    QMainWindow, QWidget {{
        background: #07101f;
        color: #eef4ff;
        font-family: Arial;
    }}
    QLabel {{
        background: transparent;
    }}

    QFrame#exchangeRateBar {{
        background: #0b1424;
        border-bottom: 1px solid #24334b;
    }}
    QWidget#ratesViewport,
    QWidget#ratesTrack,
    QWidget#ratesGroup,
    QWidget#rateEntry {{
        background: transparent;
    }}
    QLabel#rateSymbol {{
        color: #93a0b5;
        font-size: {max(metrics.body_size - 2, 11)}px;
        letter-spacing: 1px;
    }}
    QLabel#rateValue {{
        color: #f6f8fc;
        font-size: {metrics.body_size}px;
        font-weight: 800;
    }}
    QLabel#rateUp {{
        color: #2dd4bf;
        font-size: {max(metrics.body_size - 2, 11)}px;
        font-weight: 700;
    }}
    QLabel#rateDown {{
        color: #fb7185;
        font-size: {max(metrics.body_size - 2, 11)}px;
        font-weight: 700;
    }}
    QLabel#rateNeutral {{
        color: #94a3b8;
        font-size: {max(metrics.body_size - 2, 11)}px;
        font-weight: 700;
    }}

    QFrame#mediaPanel {{
        background: #05080f;
        border: 1px solid #2d405d;
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

    QFrame#referencesPanel {{
        background: #101a2e;
        border: 1px solid #2a3b58;
        border-radius: 16px;
    }}
    QLabel#cardTitle {{
        color: #a9bddc;
        font-size: {max(metrics.title_size - 1, 12)}px;
        font-weight: 800;
        letter-spacing: 0px;
    }}
    QLabel#referencesCount {{
        color: #7186a8;
        font-size: {small_text}px;
    }}
    QFrame#referenceItem {{
        background: #0b1424;
        border: 1px solid #263a58;
        border-radius: 11px;
    }}
    QLabel#referenceCodeBadge {{
        color: #7689a6;
        background: #09111f;
        border: 1px solid #263a58;
        border-radius: 5px;
        padding: 3px 5px;
        font-size: {badge_text}px;
        font-family: Consolas;
    }}
    QLabel#referenceTitle {{
        color: #f2f5fb;
        font-size: {max(metrics.body_size - 2, 11)}px;
        font-weight: 800;
    }}
    QLabel#referenceLocation {{
        color: #8493ac;
        font-size: {badge_text}px;
    }}
    QLabel#operationImport {{
        color: #e7b454;
        background: #302b24;
        border-radius: 8px;
        padding: 2px 7px;
        font-size: {badge_text}px;
        font-weight: 800;
    }}
    QLabel#operationExport {{
        color: #2dd4bf;
        background: #123036;
        border-radius: 8px;
        padding: 2px 7px;
        font-size: {badge_text}px;
        font-weight: 800;
    }}
    QLabel#statusDelivered {{
        color: #2dd4bf;
        background: #0b3437;
        border-radius: 8px;
        padding: 2px 7px;
        font-size: {badge_text}px;
        font-weight: 800;
    }}
    QLabel#statusPending {{
        color: #fb7185;
        background: #392337;
        border-radius: 8px;
        padding: 2px 7px;
        font-size: {badge_text}px;
        font-weight: 800;
    }}
    QLabel#statusProgress {{
        color: #e7b454;
        background: #302b24;
        border-radius: 8px;
        padding: 2px 7px;
        font-size: {badge_text}px;
        font-weight: 800;
    }}
    QLabel#emptyState {{
        color: #71839e;
        font-size: {metrics.body_size}px;
    }}

    QLabel#applicationStatusBar {{
        background: #0b1424;
        color: #90a3c0;
        border-top: 1px solid #26334a;
        padding-left: 14px;
        font-size: {small_text}px;
    }}
    QMainWindow[appState="Degraded"] QLabel#applicationStatusBar {{
        color: #f6c85f;
    }}

    QScrollArea,
    QWidget#referencesViewport,
    QScrollArea > QWidget > QWidget {{
        background: transparent;
        border: none;
    }}
    """
