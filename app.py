import streamlit as st
import requests

# CONFIGURATION - Now using Streamlit Secrets for safety
# Make sure to add TMDB_API_KEY in your Streamlit Cloud settings!
try:
    API_KEY = st.secrets["TMDB_API_KEY"]
except:
    st.error("Missing API Key! Please add 'TMDB_API_KEY' to your Streamlit Secrets.")
    st.stop()

BASE_URL = "https://api.themoviedb.org/3"

# STRICT LIST of your UK services
MY_SERVICES = [
    "Netflix", "Amazon Prime Video", "Disney Plus", "Apple TV Plus",
    "Now TV", "BBC iPlayer", "ITVX", "Channel 4", "My5", "UKTV Play"
]

st.set_page_config(page_title="The Couple's Couch", layout="wide")
st.title("🎬 The Couple's Couch: Maz & You")

# Persistent Taste Profile logic can go here in the future
if 'liked_ids' not in st.session_state:
    st.session_state.liked_ids = []
if 'liked_names' not in st.session_state:
    st.session_state.liked_names = []

def get_uk_providers(item_id, media_type):
    url = f"{BASE_URL}/{media_type}/{item_id}/watch/providers?api_key={API_KEY}"
    res = requests.get(url).json()
    uk_data = res.get('results', {}).get('GB', {})
    all_options = uk_data.get('flatrate', []) + uk_data.get('free', []) + uk_data.get('ads', [])
    return list(set([p['provider_name'] for p in all_options if p['provider_name'] in MY_SERVICES]))

def get_filtered_recs():
    if not st.session_state.liked_ids: return []
    last_id = st.session_state.liked_ids[-1]
    recs = []
    for m_type in ["tv", "movie"]:
        url = f"{BASE_URL}/{m_type}/{last_id}/recommendations?api_key={API_KEY}&region=GB"
        results = requests.get(url).json().get('results', [])
        for r in results:
            providers = get_uk_providers(r['id'], m_type)
            if providers:
                r['found_on'] = providers
                recs.append(r)
    return sorted(recs, key=lambda x: x.get('vote_average', 0), reverse=True)[:10]

with st.sidebar:
    st.header("🧠 Train the Engine")
    query = st.text_input("A show you both liked...")
    if query:
        search_results = requests.get(f"{BASE_URL}/search/multi?api_key={API_KEY}&query={query}&region=GB").json().get('results', [])[:3]
        for r in search_results:
            name = r.get('name') or r.get('title')
            if st.button(f"Add '{name}'", key=f"add_{r['id']}"):
                st.session_state.liked_ids.append(r['id'])
                st.session_state.liked_names.append(name)
                st.rerun()
    st.write("---")
    st.write("**Taste Profile:**", ", ".join(st.session_state.liked_names))
    if st.button("Reset Profile"):
        st.session_state.liked_ids = []
        st.session_state.liked_names = []
        st.rerun()

if st.session_state.liked_ids:
    if st.button("What's on Tonight?"):
        recommendations = get_filtered_recs()
        if recommendations:
            for r in recommendations:
                col1, col2 = st.columns([1, 4])
                with col1:
                    if r.get('poster_path'): st.image(f"https://image.tmdb.org/t/p/w200{r['poster_path']}")
                with col2:
                    st.subheader(r.get('name') or r.get('title'))
                    st.info(f"📍 **Watch on:** {', '.join(r['found_on'])}")
                    st.write(r.get('overview'))
                st.divider()
        else:
            st.warning("No matches on your platforms yet. Add more variety!")
else:
    st.info("👈 Use the sidebar to add a show you and Maz enjoyed.")
