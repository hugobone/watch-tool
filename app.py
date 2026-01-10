import streamlit as st
import requests
import random

# --- 1. SETUP & SECRETS ---
st.set_page_config(page_title="The Couple's Couch", page_icon="🍿", layout="wide")

# Try to get the API Key safely
try:
    API_KEY = st.secrets["TMDB_API_KEY"]
except FileNotFoundError:
    st.error("⚠️ API Key is missing! Please go to your Streamlit App Settings > Secrets and add 'TMDB_API_KEY'.")
    st.stop()

BASE_URL = "https://api.themoviedb.org/3"

# Your specific UK services (Added 'All 4' just in case TMDB uses the old name)
MY_SERVICES = [
    "Netflix", "Amazon Prime Video", "Disney Plus", "Apple TV Plus",
    "Now TV", "BBC iPlayer", "ITVX", "Channel 4", "All 4", "My5", "UKTV Play"
]

# --- 2. "MEMORY" (SESSION STATE) ---
if 'liked_ids' not in st.session_state:
    st.session_state.liked_ids = []
if 'liked_names' not in st.session_state:
    st.session_state.liked_names = []

# --- 3. THE BRAINS (FUNCTIONS) ---
def search_tmdb(query):
    """Searches for movies/TV shows matching the query."""
    url = f"{BASE_URL}/search/multi?api_key={API_KEY}&query={query}&include_adult=false&language=en-US&page=1"
    try:
        response = requests.get(url)
        response.raise_for_status() # Check for errors
        return response.json().get('results', [])
    except Exception as e:
        st.error(f"Error talking to TMDB: {e}")
        return []

def get_uk_providers(item_id, media_type):
    """Finds where a show is streaming in the GB region."""
    url = f"{BASE_URL}/{media_type}/{item_id}/watch/providers?api_key={API_KEY}"
    try:
        data = requests.get(url).json()
        uk_data = data.get('results', {}).get('GB', {})
        
        # Combine Flatrate (Subscription), Free, and Ads options
        options = uk_data.get('flatrate', []) + uk_data.get('free', []) + uk_data.get('ads', [])
        
        # Filter: Keep only the ones in your MY_SERVICES list
        my_matches = [p['provider_name'] for p in options if p['provider_name'] in MY_SERVICES]
        return list(set(my_matches))
    except:
        return []

def get_recommendations():
    """Finds recommendations based on your liked shows."""
    if not st.session_state.liked_ids:
        return []
    
    # Use the last added show to seed recommendations
    seed_id = st.session_state.liked_ids[-1]
    recommendations = []
    
    # Search both Movies and TV shows related to the seed
    for media_type in ['movie', 'tv']:
        url = f"{BASE_URL}/{media_type}/{seed_id}/recommendations?api_key={API_KEY}&language=en-US&page=1"
        data = requests.get(url).json().get('results', [])
        
        for item in data[:12]: # Check top 12 matches
            # Only keep it if it's on YOUR services
            providers = get_uk_providers(item['id'], media_type)
            if providers:
                item['my_providers'] = providers
                item['media_type'] = media_type # Save if it's movie or tv
                recommendations.append(item)
                
    return recommendations

# --- 4. THE INTERFACE ---

st.title("🍿 The Couple's Couch")
st.markdown("Your custom UK streaming engine.")

# --- SIDEBAR: INPUT ---
with st.sidebar:
    st.header("1. Build Your Taste")
    st.info("Type a show you love (e.g. 'The Bear') and hit Enter.")
    
    # Search Input
    search_query = st.text_input("Search for a show:", placeholder="Type here...")

    if search_query:
        st.write("🔎 **Searching...**")
        results = search_tmdb(search_query)
        
        if not results:
            st.warning("No results found. Check spelling!")
        else:
            st.write(f"Found {len(results[:3])} matches:")
            # Display buttons for top 3 results
            for item in results[:3]:
                title = item.get('name') or item.get('title')
                date = item.get('first_air_date') or item.get('release_date') or "Unknown Date"
                
                # The "Add" Button
                if st.button(f"➕ Add: {title} ({date[:4]})", key=item['id']):
                    # When clicked:
                    st.session_state.liked_ids.append(item['id'])
                    st.session_state.liked_names.append(title)
                    st.success(f"Added **{title}**!")
                    st.rerun() # Refresh the page instantly

    st.divider()
    
    # Show current list
    if st.session_state.liked_names:
        st.write("### ❤️ Your Profile:")
        for name in st.session_state.liked_names:
            st.write(f"- {name}")
        
        if st.button("🗑️ Reset Profile"):
            st.session_state.liked_ids = []
            st.session_state.liked_names = []
            st.rerun()

# --- MAIN PAGE: OUTPUT ---

if not st.session_state.liked_ids:
    st.info("👈 **Start by adding a show in the sidebar!** The engine needs to know what you like first.")

else:
    st.write("---")
    st.header("2. Tonight's Recommendations")
    
    col_a, col_b = st.columns(2)
    with col_a:
        do_search = st.button("🔎 Find Matches on My Apps", type="primary")
    with col_b:
        do_lucky = st.button("🎲 I'm Feeling Lucky (Pick 1)", type="secondary")

    if do_search or do_lucky:
        with st.spinner("Checking Netflix, Prime, Disney+ and others..."):
            recs = get_recommendations()
            
            if not recs:
                st.warning(f"We found recommendations, but **none of them are on your specific services** right now. Try adding a different show to the profile!")
            
            else:
                # If "Lucky" was clicked, pick just one
                if do_lucky:
                    recs = [random.choice(recs)]
                    st.balloons()

                # Display Results
                for show in recs:
                    with st.container():
                        c1, c2 = st.columns([1, 4])
                        with c1:
                            if show.get('poster_path'):
                                st.image(f"https://image.tmdb.org/t/p/w200{show['poster_path']}")
                        with c2:
                            st.subheader(show.get('name') or show.get('title'))
                            st.markdown(f"**📺 Watch it on:** {', '.join(show['my_providers'])}")
                            st.caption(show.get('overview'))
                        st.divider()
