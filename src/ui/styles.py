"""
UI Styles module
Defines custom CSS for the Streamlit app.
Adheres to ui-skills: no gradients, flat design, professional color scheme.
"""

def get_custom_css() -> str:
    """Returns the custom CSS for the application."""
    return """
<style>
    /* ========================================
       Color Tokens (Financial Professional Theme)
       ======================================== */
    :root {
        --color-bg-primary: #ffffff;
        --color-bg-secondary: #f8f9fa;
        --color-bg-tertiary: #e9ecef;
        --color-text-primary: #212529;
        --color-text-secondary: #495057;
        --color-text-muted: #6c757d;
        --color-accent: #0066cc;
        --color-positive: #10b981; /* emerald-500 */
        --color-negative: #ef4444; /* red-500 */
        --color-neutral: #6c757d;
        --color-border: #dee2e6;
        --radius-sm: 4px;
        --radius-md: 8px;
        --radius-lg: 12px;
        --shadow-sm: 0 1px 2px rgba(0,0,0,0.05);
        --shadow-md: 0 2px 4px rgba(0,0,0,0.08);
    }

    /* ========================================
       Common Utilities
       ======================================== */
    .metric-group {
        background-color: var(--color-bg-secondary);
        border: 1px solid var(--color-border);
        border-radius: var(--radius-md);
        padding: 0.75rem 1rem;
        height: 100%;
        box-shadow: var(--shadow-sm);
    }
    
    .metric-title {
        font-size: 0.85rem;
        font-weight: 700;
        color: var(--color-text-secondary);
        margin-bottom: 0.75rem;
        border-bottom: 2px solid var(--color-border);
        padding-bottom: 0.25rem;
    }
    
    .metric-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 0.4rem;
        font-size: 0.9rem;
    }
    
    .metric-label {
        color: var(--color-text-muted);
        font-size: 0.8rem;
    }
    
    .metric-value {
        font-weight: 600;
        color: var(--color-text-primary);
        font-variant-numeric: tabular-nums;
    }
    
    .text-positive { color: var(--color-positive) !important; }
    .text-negative { color: var(--color-negative) !important; }
    .text-neutral { color: var(--color-neutral) !important; }

    /* ========================================
       Base Styles
       ======================================== */
    .main-header {
        font-size: 1.75rem;
        font-weight: 600;
        color: var(--color-text-primary);
        margin-bottom: 1.5rem;
        letter-spacing: -0.02em;
    }

    /* ========================================
       Card Components
       ======================================== */
    .metric-card {
        background-color: var(--color-bg-secondary);
        border: 1px solid var(--color-border);
        padding: 1rem;
        border-radius: var(--radius-md);
        color: var(--color-text-primary);
        box-shadow: var(--shadow-sm);
    }

    .flash-summary {
        background-color: var(--color-bg-secondary);
        color: var(--color-text-primary);
        padding: 1rem 1.25rem;
        border-radius: var(--radius-md);
        font-family: 'SF Mono', 'Consolas', monospace;
        font-size: 0.875rem;
        line-height: 1.6;
        white-space: pre-wrap;
        border: 1px solid var(--color-border);
    }

    /* ========================================
       Theme Ranking
       ======================================== */
    .theme-rank {
        padding: 0.75rem 1rem;
        margin: 0.25rem 0;
        border-radius: var(--radius-sm);
        border-left: 3px solid transparent;
    }
    
    .positive {
        background-color: #d1fae5; /* green-100 */
        color: #065f46; /* green-800 */
        border-left-color: var(--color-positive);
    }
    
    .negative {
        background-color: #fee2e2; /* red-100 */
        color: #991b1b; /* red-800 */
        border-left-color: var(--color-negative);
    }

    /* ========================================
       Sentiment Indicators
       ======================================== */
    .sentiment-bullish {
        color: var(--color-positive);
        font-weight: 600;
    }
    
    .sentiment-bearish {
        color: var(--color-negative);
        font-weight: 600;
    }
    
    .sentiment-neutral {
        color: var(--color-neutral);
        font-weight: 600;
    }

    /* ========================================
       Button Overrides
       ======================================== */
    .stButton button {
        border-radius: var(--radius-sm);
        font-weight: 500;
        transition: background-color 0.15s ease;
    }
    
    /* Primary button - 青系に統一 */
    .stButton button[kind="primary"],
    .stButton button[data-baseweb="button"][kind="primary"] {
        background-color: #2563eb !important;
        color: white !important;
    }
    
    .stButton button[kind="primary"]:hover,
    .stButton button[data-baseweb="button"][kind="primary"]:hover {
        background-color: #1d4ed8 !important;
    }
    
    /* Streamlit 1.35+ のprimary button対応 */
    [data-testid="stBaseButton-primary"] {
        background-color: #2563eb !important;
        color: white !important;
    }
    
    [data-testid="stBaseButton-primary"]:hover {
        background-color: #1d4ed8 !important;
    }

    /* ========================================
       Expander Styling
       ======================================== */
    .streamlit-expanderHeader {
        font-size: 0.875rem;
        font-weight: 500;
        color: var(--color-text-secondary);
    }

    /* ========================================
       Metric Improvements
       ======================================== */
    [data-testid="stMetricValue"] {
        font-size: 1.25rem;
        font-weight: 600;
        font-variant-numeric: tabular-nums;
    }

    [data-testid="stMetricLabel"] {
        font-size: 0.75rem;
        color: var(--color-text-muted);
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    /* ========================================
       Tab Styling
       ======================================== */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.5rem;
    }

    .stTabs [data-baseweb="tab"] {
        padding: 0.5rem 1rem;
        font-weight: 500;
    }

    /* ========================================
       Divider
       ======================================== */
    hr {
        border: none;
        border-top: 1px solid var(--color-border);
        margin: 1.5rem 0;
    }

    /* ========================================
       Dark Mode Support (Streamlit native)
       ======================================== */
    @media (prefers-color-scheme: dark) {
        :root {
            --color-bg-primary: #0e1117;
            --color-bg-secondary: #1a1d24;
            --color-bg-tertiary: #262b36;
            --color-text-primary: #fafafa;
            --color-text-secondary: #b0b8c1;
            --color-text-muted: #6b7280;
            --color-border: #374151;
        }
    }
</style>
"""
