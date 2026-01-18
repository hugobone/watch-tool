import streamlit as st
import requests
import random
import json
import os
from pathlib import Path

# --- 1. SETUP & SECRETS ---
st.set_page_config(page_title="The Couple's Couch", page_icon="🍿", layout="wide")

try:
    API_KEY = st.secrets["TMDB_API_KEY"]
except FileNotFoundError:
    st.error("⚠️ API Key is missing! Check Streamlit Secrets.")
    st.stop()

BASE_URL = "https://api.themoviedb.org/3"

# --- 2. SERVICES & CONFIG ---
MY_SERVICES = [
    "Netflix", "Amazon Prime Video", "Disney+", "Apple TV+",
    "Now TV", "BBC iPlayer", "ITVX", "Channel 4", "My5",
    "UKTV Play", "Paramount+", "Discovery+"
]

MIN_VOTE_AVERAGE = 6.0
MIN_VOTE_COUNT = 50

# --- 3. PERSISTENT STORAGE ---
DATA_FILE = Path("user_data.json")

def load_user_data():
    """Load saved data from file"""
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
                return data.get('liked_items', []), data.get('watch_later', [])
        except Exception as e:
            st.warning(f"Couldn't load saved data: {e}")
    return [], []

def save_user_data():
    """Save data to file"""
    try:
        data = {
            'liked_items': st.session_state.liked_items,
            'watch_later': st.session_state.watch_later
        }
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        st.error(f"Couldn't save data: {e}")

# Initialize session state with saved data
if 'liked_items' not in st.session_state:
    liked, watch_later = load_user_data()
    st.session_state.liked_items = liked
    st.session_state.watch_later = watch_later
    st.session_state.data_loaded = True

# --- 4. CACHING & API FUNCTIONS ---
@st.cache_data(ttl=3600)
def search_tmdb(query):
    """Cached search - results valid for 1 hour"""
    url = f"{BASE_URL}/search/multi?api_key={API_KEY}&query={query}&include_adult=false&language=en-US&page=1"
    try:
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        return resp.json().get('results', [])
    except Exception as e:
        st.error(f"Search failed: {e}")
        return []

@st.cache_data(ttl=3600)
def get_uk_providers(item_id, media_type):
    """Cached provider lookup"""
    url = f"{BASE_URL}/{media_type}/{item_id}/watch/providers?api_key={API_KEY}"
    try:
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        uk_data = data.get('results', {}).get('GB', {})
        
        options = (uk_data.get('flatrate', []) + 
                  uk_data.get('free', []) + 
                  uk_data.get('ads', []))
        
        return [p['provider_name'] for p in options if p['provider_name'] in MY_SERVICES]
    except Exception as e:
        return []

def get_recommendations_multi_seed():
    """Get recommendations from multiple liked items and combine results"""
    if not st.session_state.liked_items:
        return [], []
    
    all_valid = []
    all_fallback = []
    seen_ids = set()
    
    # Get IDs of already liked items to filter them out
    liked_ids = {item['id'] for item in st.session_state.liked_items}
    
    seeds = st.session_state.liked_items[-3:]
    
    for seed in seeds:
        seed_id = seed['id']
        media_type = seed['media_type']
        
        url = f"{BASE_URL}/{media_type}/{seed_id}/recommendations?api_key={API_KEY}&language=en-US&page=1"
        
        try:
            resp = requests.get(url, timeout=5)
            resp.raise_for_status()
            results = resp.json().get('results', [])
            
            for item in results[:15]:
                # Skip if already in seen or already liked
                if item['id'] in seen_ids or item['id'] in liked_ids:
                    continue
                seen_ids.add(item['id'])
                
                if item.get('vote_average', 0) < MIN_VOTE_AVERAGE:
                    continue
                if item.get('vote_count', 0) < MIN_VOTE_COUNT:
                    continue
                
                item['media_type'] = media_type
                item['seed_name'] = seed['name']
                
                providers = get_uk_providers(item['id'], media_type)
                
                if providers:
                    item['my_providers'] = providers
                    all_valid.append(item)
                else:
                    all_fallback.append(item)
                    
        except Exception as e:
            st.warning(f"Couldn't get recommendations from {seed['name']}: {e}")
            continue
    
    all_valid.sort(key=lambda x: x.get('vote_average', 0), reverse=True)
    all_fallback.sort(key=lambda x: x.get('vote_average', 0), reverse=True)
    
    return all_valid[:12], all_fallback[:6]

# --- 5. UI COMPONENTS ---
def render_item_card(item, show_seed=False, show_add_to_watchlist=True):
    """Reusable card component"""
    c1, c2 = st.columns([1, 4])
    
    with c1:
        if item.get('poster_path'):
            st.image(f"https://image.tmdb.org/t/p/w200{item['poster_path']}")
        else:
            st.write("🎬")
    
    with c2:
        title = item.get('name') or item.get('title', 'Unknown')
        rating = item.get('vote_average', 0)
        st.subheader(f"{title} ⭐ {rating:.1f}")
        
        if 'my_providers' in item:
            st.success(f"✅ **Available on:** {', '.join(item['my_providers'])}")
        else:
            st.info("🌍 Not on your services (Check Rent/Buy)")
        
        if show_seed and 'seed_name' in item:
            st.caption(f"💡 Recommended because you liked: {item['seed_name']}")
        
        overview = item.get('overview', 'No description available.')
        st.write(overview[:200] + "..." if len(overview) > 200 else overview)
        
        if show_add_to_watchlist:
            item_key = f"{item['id']}_{item.get('media_type', 'unknown')}"
            
            # Create button row
            btn_col1, btn_col2 = st.columns(2)
            
            with btn_col1:
                if st.button(f"✅ Already Watched", key=f"watched_{item_key}"):
                    # Add to taste profile
                    new_item = {
                        'id': item['id'],
                        'name': title,
                        'media_type': item.get('media_type', 'unknown')
                    }
                    # Check if not already in profile
                    if not any(liked['id'] == new_item['id'] for liked in st.session_state.liked_items):
                        st.session_state.liked_items.append(new_item)
                        save_user_data()
                        st.toast(f"✅ Added '{title}' to your taste profile!", icon="✅")
                    else:
                        st.toast(f"'{title}' is already in your profile", icon="ℹ️")
            
            with btn_col2:
                if st.button(f"📌 Watch Later", key=f"wl_{item_key}"):
                    # Check if not already in watch later
                    if not any(wl['id'] == item['id'] for wl in st.session_state.watch_later):
                        st.session_state.watch_later.append(item)
                        save_user_data()
                        st.success("Added to Watch Later!")
                        st.rerun()

# --- 6. MAIN INTERFACE ---
st.title("🍿 The Couple's Couch")
st.markdown(f"**Searching:** {', '.join(MY_SERVICES)}")

# SIDEBAR - TASTE BUILDER
with st.sidebar:
    st.header("🎯 Build Your Taste Profile")
    
    query = st.text_input("Search for shows/movies:", placeholder="e.g. Slow Horses")
    
    if query:
        results = search_tmdb(query)
        if results:
            st.write(f"Found {len(results[:5])} results:")
            for item in results[:5]:
                name = item.get('name') or item.get('title')
                date = item.get('first_air_date') or item.get('release_date') or "Unknown"
                media_type = item.get('media_type', 'unknown')
                
                if item.get('poster_path'):
                    st.image(f"https://image.tmdb.org/t/p/w92{item['poster_path']}", width=50)
                
                if st.button(f"➕ {name} ({str(date)[:4]})", key=f"add_{item['id']}"):
                    new_item = {
                        'id': item['id'],
                        'name': name,
                        'media_type': media_type
                    }
                    if new_item not in st.session_state.liked_items:
                        st.session_state.liked_items.append(new_item)
                        save_user_data()
                        st.rerun()
    
    if st.session_state.liked_items:
        st.divider()
        st.write("**Your Taste Profile:**")
        for idx, item in enumerate(st.session_state.liked_items):
            col1, col2 = st.columns([4, 1])
            with col1:
                st.write(f"• {item['name']}")
            with col2:
                if st.button("❌", key=f"remove_{idx}"):
                    st.session_state.liked_items.pop(idx)
                    save_user_data()
                    st.rerun()
        
        if st.button("🗑️ Clear All", type="secondary"):
            st.session_state.liked_items = []
            save_user_data()
            st.rerun()
    
    if st.session_state.watch_later:
        st.divider()
        st.write("**📌 Watch Later:**")
        for idx, item in enumerate(st.session_state.watch_later):
            col1, col2 = st.columns([4, 1])
            with col1:
                title = item.get('name') or item.get('title', 'Unknown')
                st.write(f"• {title}")
            with col2:
                if st.button("❌", key=f"wl_remove_{idx}"):
                    st.session_state.watch_later.pop(idx)
                    save_user_data()
                    st.rerun()

# MAIN AREA - RECOMMENDATIONS
if st.session_state.liked_items:
    st.divider()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        search_btn = st.button("🔎 Find Matches", type="primary", use_container_width=True)
    with col2:
        lucky_btn = st.button("🎲 Pick for Us", type="secondary", use_container_width=True)
    with col3:
        filter_providers = st.checkbox("Only my services", value=True)

    if search_btn or lucky_btn:
        with st.spinner("Finding your perfect match..."):
            valid, fallback = get_recommendations_multi_seed()
            
            if filter_providers:
                final_list = valid
                is_fallback = False
            else:
                final_list = valid + fallback
                is_fallback = False
            
            if not final_list:
                st.error("😕 No recommendations found. Try adding more shows to your profile!")
            
            else:
                if lucky_btn:
                    winner = random.choice(final_list)
                    st.balloons()
                    st.header(f"🏆 Tonight's Pick: {winner.get('name') or winner.get('title')}")
                    
                    render_item_card(winner, show_seed=True, show_add_to_watchlist=False)
                    
                else:
                    if filter_providers and valid:
                        st.success(f"✨ Found {len(valid)} great matches on your services!")
                    elif not filter_providers:
                        st.info(f"📺 Showing {len(final_list)} recommendations (including rentals)")
                    else:
                        st.warning("⚠️ No exact matches on your services. Uncheck 'Only my services' to see more.")
                    
                    for item in final_list:
                        render_item_card(item, show_seed=True)
                        st.divider()

else:
    st.info("👈 **Get started:** Search and add shows you like in the sidebar!")
    st.markdown("""
    ### How it works:
    1. **Search** for shows/movies you both enjoy
    2. **Add them** to build your taste profile  
    3. **Get recommendations** tailored to what you actually have access to
    4. **Pick randomly** when you can't decide, or browse the full list
    
    💾 *Your profile is saved automatically and will be here next time!*
    """)
