"""Streamlit frontend for the Telecom Triage Agent API."""

import json

import requests
import streamlit as st

# FastAPI backend endpoint
TRIAGE_API_URL = "http://127.0.0.1:8000/triage"

# Map backend priority codes to customer-friendly labels
CUSTOMER_PRIORITY_LABELS = {
    "P0": "High",
    "P1": "Medium",
    "P2": "Low",
}

# Customer-friendly next steps based on issue category
CUSTOMER_NEXT_STEPS = {
    "SIM Replacement": (
        "Please restart your phone once. If the issue persists, "
        "visit the nearest service center with a valid ID."
    ),
    "Porting": (
        "Please ensure your UPC is still valid and wait for the port confirmation SMS. "
        "Contact support if the transfer takes longer than 72 hours."
    ),
    "Recharge Failure": (
        "Please check your payment confirmation message or bank statement. "
        "If the amount was deducted, wait up to 30 minutes for balance to update."
    ),
    "Billing Issues": (
        "Please review your latest bill in the self-care portal. "
        "Our billing team will verify any disputed charges and update you shortly."
    ),
    "Network Issues": (
        "Please restart your device and toggle airplane mode for 30 seconds. "
        "If service does not return, check for outages in your area."
    ),
}

# Estimated resolution windows based on priority
ESTIMATED_RESOLUTION = {
    "P0": "Within 2 hours",
    "P1": "Within 24 hours",
    "P2": "Within 48 hours",
}

# Admin priority badge colors
PRIORITY_BADGE_STYLES = {
    "P0": ("#dc3545", "#ffffff"),  # Red
    "P1": ("#fd7e14", "#ffffff"),  # Orange
    "P2": ("#28a745", "#ffffff"),  # Green
}


def inject_custom_styles() -> None:
    """Apply dark-theme-friendly spacing, cards, and badge styling."""
    st.markdown(
        """
        <style>
            .block-container {
                padding-top: 2rem;
                padding-bottom: 2rem;
            }

            .triage-card {
                background-color: rgba(255, 255, 255, 0.04);
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 14px;
                padding: 1.25rem 1.5rem;
                margin-bottom: 1rem;
            }

            .triage-card h3 {
                margin-top: 0;
                margin-bottom: 0.75rem;
                font-size: 1.1rem;
                letter-spacing: 0.02em;
            }

            .info-row {
                margin-bottom: 0.9rem;
            }

            .info-label {
                font-size: 0.82rem;
                text-transform: uppercase;
                letter-spacing: 0.06em;
                opacity: 0.72;
                margin-bottom: 0.15rem;
            }

            .info-value {
                font-size: 1rem;
                line-height: 1.5;
            }

            .priority-badge {
                display: inline-block;
                padding: 0.25rem 0.75rem;
                border-radius: 999px;
                font-size: 0.85rem;
                font-weight: 700;
                letter-spacing: 0.03em;
            }

            .status-badge {
                display: inline-block;
                padding: 0.25rem 0.75rem;
                border-radius: 999px;
                font-size: 0.85rem;
                font-weight: 600;
                background-color: rgba(13, 110, 253, 0.18);
                color: #8ec5ff;
                border: 1px solid rgba(13, 110, 253, 0.35);
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def priority_badge_html(priority: str) -> str:
    """Return a colored HTML badge for admin priority display."""
    bg_color, text_color = PRIORITY_BADGE_STYLES.get(priority, ("#6c757d", "#ffffff"))
    label = priority if priority in PRIORITY_BADGE_STYLES else priority or "N/A"
    return (
        f'<span class="priority-badge" style="background-color:{bg_color};'
        f'color:{text_color};">{label}</span>'
    )


def customer_priority_label(priority: str) -> str:
    """Convert P0/P1/P2 into customer-friendly priority text."""
    return CUSTOMER_PRIORITY_LABELS.get(priority, priority or "Standard")


def customer_next_step(category: str) -> str:
    """Generate a helpful next-step message for the customer."""
    if category in CUSTOMER_NEXT_STEPS:
        return CUSTOMER_NEXT_STEPS[category]

    return (
        "Our support team is reviewing your complaint. "
        "Please keep your phone nearby for updates."
    )


def estimated_resolution_time(priority: str) -> str:
    """Return an estimated resolution window for the customer view."""
    return ESTIMATED_RESOLUTION.get(priority, "Within 48 hours")


def analyze_complaint(customer_id: str, location: str, complaint: str) -> dict | None:
    """Send the complaint to the triage API and return the JSON response."""
    payload = {
        "customer_id": customer_id.strip(),
        "message": complaint.strip(),
        "location": location.strip() or None,
    }

    try:
        response = requests.post(TRIAGE_API_URL, json=payload, timeout=60)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError:
        st.error(
            "Could not connect to the API. Make sure the FastAPI server is running at "
            "http://127.0.0.1:8000"
        )
    except requests.exceptions.Timeout:
        st.error("The request timed out. Please try again.")
    except requests.exceptions.HTTPError:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        st.error(f"API error ({response.status_code}): {detail}")
    except requests.exceptions.RequestException as exc:
        st.error(f"Request failed: {exc}")

    return None


def display_customer_view(result: dict) -> None:
    """Show a simplified, customer-friendly ticket summary."""
    category = result.get("category", "General Support")
    priority = result.get("priority", "P2")

    st.markdown("---")
    st.markdown("### Ticket Summary")

    with st.container(border=True):
        st.markdown(
            f"""
            <div class="info-row">
                <div class="info-label">Issue Category</div>
                <div class="info-value">{category}</div>
            </div>
            <div class="info-row">
                <div class="info-label">Ticket Status</div>
                <div class="info-value">
                    <span class="status-badge">Investigating</span>
                </div>
            </div>
            <div class="info-row">
                <div class="info-label">Priority</div>
                <div class="info-value">{customer_priority_label(priority)}</div>
            </div>
            <div class="info-row">
                <div class="info-label">Recommended Next Step</div>
                <div class="info-value">{customer_next_step(category)}</div>
            </div>
            <div class="info-row">
                <div class="info-label">Estimated Resolution Time</div>
                <div class="info-value">{estimated_resolution_time(priority)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def display_admin_view(result: dict) -> None:
    """Show full technical triage details for admin users."""
    category = result.get("category", "N/A")
    priority = result.get("priority", "N/A")
    next_tool = result.get("next_tool", "N/A")

    st.markdown("---")

    # Section A: Triage Summary
    st.markdown("### A. Triage Summary")
    with st.container(border=True):
        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("**Category**")
            st.markdown(f"<p style='font-size:1.05rem;'>{category}</p>", unsafe_allow_html=True)

        with col2:
            st.markdown("**Priority**")
            st.markdown(priority_badge_html(priority), unsafe_allow_html=True)

        with col3:
            st.markdown("**Selected Tool**")
            st.markdown(f"<p style='font-size:1.05rem;'>{next_tool}</p>", unsafe_allow_html=True)

    st.markdown("")

    # Section B: AI Reasoning
    st.markdown("### B. AI Reasoning")
    with st.container(border=True):
        st.markdown("**Reasoning**")
        st.write(result.get("reasoning", "N/A"))
        st.markdown("**Why**")
        st.write(result.get("why", "N/A"))

    st.markdown("")

    # Section C: Customer / Tool Information
    st.markdown("### C. Customer / Tool Information")
    with st.container(border=True):
        tool_result = result.get("tool_result")
        if tool_result:
            st.code(json.dumps(tool_result, indent=2), language="json")
        else:
            st.info("No tool result was returned for this complaint.")


def main() -> None:
    """Build the Streamlit page."""
    st.set_page_config(
        page_title="Telecom Triage Agent",
        page_icon="📡",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    inject_custom_styles()

    st.title("Telecom Triage Agent")
    st.markdown(
        "AI-powered support ticket triage for telecom complaints. "
        "Submit a complaint to receive issue classification, priority, "
        "and recommended next actions."
    )

    st.markdown("")

    # Role selector at the top of the page
    role = st.radio(
        "Role",
        options=["Customer", "Admin"],
        horizontal=True,
        help="Customer view shows simplified ticket updates. Admin view shows full technical details.",
    )

    st.markdown("")

    # Complaint input form
    with st.form("triage_form"):
        customer_id = st.text_input(
            "Customer ID",
            placeholder="e.g. CUST1001",
        )
        location = st.text_input(
            "Location",
            placeholder="e.g. Mumbai",
        )
        complaint = st.text_area(
            "Complaint",
            placeholder="Describe the customer's issue...",
            height=150,
        )
        submitted = st.form_submit_button("Analyze Complaint", type="primary", use_container_width=True)

    if submitted:
        if not customer_id.strip():
            st.error("Customer ID is required.")
            return
        if not complaint.strip():
            st.error("Complaint is required.")
            return

        with st.spinner("Analyzing complaint..."):
            result = analyze_complaint(customer_id, location, complaint)

        if result:
            if role == "Customer":
                display_customer_view(result)
            else:
                display_admin_view(result)


if __name__ == "__main__":
    main()
