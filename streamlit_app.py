
"""
TripMate AI - Streamlit Frontend

Run with:
streamlit run app.py
"""

from datetime import date, timedelta
from uuid import uuid4

import requests
import streamlit as st


# ============================================================
# 1. SETTINGS
# ============================================================

API_URL = "https://tripmateai-a-multi-agent-travel-planner-915h.onrender.com"

DESTINATIONS = {
    "🇯🇵 Japan": "Japan",
    "🇦🇪 Dubai": "Dubai",
    "🇹🇭 Thailand": "Thailand",
    "🇸🇬 Singapore": "Singapore",
    "🇲🇾 Malaysia": "Malaysia",
    "🇫🇷 France": "France",
    "🇮🇹 Italy": "Italy",
    "🇬🇧 United Kingdom": "United Kingdom",
    "🇨🇭 Switzerland": "Switzerland",
    "🇳🇵 Nepal": "Nepal",
}

st.set_page_config(
    page_title="TripMate AI",
    page_icon="✈️",
    layout="wide",
)


# ============================================================
# 2. CUSTOM CSS
# ============================================================

st.markdown(
    """
    <style>

    @import url(
        'https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700;800;900&display=swap'
    );

    /* Main colorful heading */
    .title {
        font-family: 'Poppins', sans-serif;
        font-size: 3.8rem;
        font-weight: 900;
        letter-spacing: 2px;
        line-height: 1.2;

        background: linear-gradient(
            90deg,
            #00C6FF,
            #0072FF,
            #8B5CF6,
            #FF4D8D,
            #FF9F43
        );

        -webkit-background-clip: text;
        background-clip: text;
        -webkit-text-fill-color: transparent;

        display: inline-block;
        margin: 0 0 8px 0;
    }

    /* Subtitle */
    .tagline {
        font-family: 'Poppins', sans-serif;
        font-size: 1rem;
        opacity: 0.75;
        margin-bottom: 25px;
    }

    /* Rounded buttons */
    div.stButton > button {
        border-radius: 12px;
        min-height: 44px;
        font-weight: 600;
    }

    /* Rounded chat messages */
    [data-testid="stChatMessage"] {
        border-radius: 16px;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# 3. SESSION STATE
# ============================================================

# Keep messages when Streamlit refreshes.
st.session_state.setdefault("messages", [])

# Keep the same conversation ID.
st.session_state.setdefault("thread_id", str(uuid4()))

# Store destination button selections.
st.session_state.setdefault("pending_prompt", None)


# ============================================================
# 4. HELPER FUNCTIONS
# ============================================================

@st.cache_data(ttl=10)
def backend_is_online():

    """Check whether FastAPI is running."""

    try:
        response = requests.get(
            f"{API_URL}/health",
            timeout=3
        )

        return response.ok

    except requests.RequestException:
        return False


def clean_answer(text):

    """Format the answer before displaying it."""

    return text.replace("$", "\\$").replace("<br>", "; ")


def ask_backend(prompt, travel_date):

    """Send the user's message to FastAPI."""

    payload = {
        "message": prompt,
        "thread_id": st.session_state.thread_id,
        "travel_date": travel_date.isoformat(),
    }

    response = requests.post(
        f"{API_URL}/chat",
        json=payload,
        timeout=180,
    )

    response.raise_for_status()

    data = response.json()

    # Update conversation ID.
    st.session_state.thread_id = data.get(
        "thread_id",
        st.session_state.thread_id
    )

    return data.get(
        "answer",
        "No answer was returned."
    )


# ============================================================
# 5. SIDEBAR - TRIP SETTINGS
# ============================================================

online = backend_is_online()

with st.sidebar:

    st.header("⚙️ Trip Settings")

    departure_date = st.date_input(
        "Departure date",
        value=date.today() + timedelta(days=7),
        min_value=date.today() + timedelta(days=1),
    )

    days = st.slider(
        "Trip length (days)",
        min_value=2,
        max_value=21,
        value=7,
    )

    budget = st.number_input(
        "Budget in NPR (optional)",
        min_value=0,
        step=10000,
        value=0,
        help="Leave 0 for no budget limit.",
    )

    style = st.radio(
        "Travel style",
        ["Budget", "Comfort", "Luxury"],
        horizontal=True,
    )

    st.divider()

    # Start a fresh conversation.
    if st.button(
        "＋ New conversation",
        use_container_width=True
    ):

        st.session_state.messages = []
        st.session_state.thread_id = str(uuid4())
        st.session_state.pending_prompt = None

        st.rerun()

    st.divider()

    # Backend status.
    if online:
        st.success("Backend online")
    else:
        st.error("Backend offline. Start FastAPI first.")


# ============================================================
# 6. MAIN HEADING
# ============================================================

st.markdown(
    '<h1 class="title">✈️ TripMate AI</h1>',
    unsafe_allow_html=True,
)

st.markdown(
    """
    <p class="tagline">
        Your smart travel planner.
        Pick a destination or type your own idea.
    </p>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# 7. DESTINATION SELECTION
# ============================================================

st.subheader("🌍 Explore Destinations")

st.caption(
    "Select a destination to start planning your trip."
)

# Searchable destination dropdown.
selected_destination = st.selectbox(
    "Search or select a country",
    options=["Choose a destination"] + list(DESTINATIONS.keys()),
    index=0,
)

if st.button(
    "✈️ Plan Selected Destination",
    use_container_width=True
):

    if selected_destination == "Choose a destination":

        st.warning("Please select a destination first.")

    else:

        place = DESTINATIONS[selected_destination]

        prompt = (
            f"Plan a {days}-day trip to {place} "
            f"from Nepal. "
            f"Travel style: {style}. "
            f"Departure date: {departure_date.isoformat()}."
        )

        if budget > 0:
            prompt += f" Total budget: NPR {budget:,}."

        st.session_state.pending_prompt = prompt


# ============================================================
# 8. SHOW CONVERSATION HISTORY
# ============================================================

st.divider()

st.subheader("💬 TripMate Conversation")

if not st.session_state.messages:

    st.info(
        "No messages yet. Select a destination above "
        "or type your own travel idea below."
    )


# Display previous messages.
for message in st.session_state.messages:

    avatar = "🧳" if message["role"] == "user" else "✈️"

    with st.chat_message(
        message["role"],
        avatar=avatar
    ):

        st.markdown(clean_answer(message["content"]))


# ============================================================
# 9. CHAT INPUT
# ============================================================

typed_message = st.chat_input(
    "Example: I want to visit Japan for 7 days..."
)


# Destination selection or normal chat message.
prompt = st.session_state.pending_prompt or typed_message


# ============================================================
# 10. SEND MESSAGE TO FASTAPI
# ============================================================

if prompt:

    # Clear pending destination selection.
    st.session_state.pending_prompt = None

    # Add user message to conversation history.
    st.session_state.messages.append(
        {
            "role": "user",
            "content": prompt,
        }
    )

    with st.chat_message("user", avatar="🧳"):

        st.markdown(prompt)

    with st.chat_message("assistant", avatar="✈️"):

        if not online:

            st.error(
                "Backend is offline. Start FastAPI and try again."
            )

        else:

            try:

                with st.spinner("✈️ TripMate is planning your trip..."):

                    answer = ask_backend(
                        prompt,
                        departure_date
                    )

                st.markdown(clean_answer(answer))

                # Save assistant response.
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": answer,
                    }
                )

            except requests.exceptions.Timeout:

                st.error(
                    "The request took too long. Please try again."
                )

            except requests.exceptions.HTTPError as error:

                st.error(
                    f"Backend error: {error.response.text}"
                )

            except requests.exceptions.RequestException as error:

                st.error(
                    f"Could not reach the backend: {error}"
                )
