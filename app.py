import streamlit as st
import requests
from PIL import Image
import pytesseract
import re
from io import BytesIO
import pandas as pd

# --- Configuration ---
IMAGE_URL = "https://srtaivedds.com/Images/Cameras/75B-002.0-CMS-CAM01-00001.jpg"

# KNOWN ORDER of destinations on this specific sign (Top to Bottom)
# We use this because the OCR cannot read the names on the left.
SIGN_ORDER = [
    {"name": "Roswell Rd",   "dist": 6.0},  # 1st Price on sign
    {"name": "Big Shanty",   "dist": 12.0}, # 2nd Price on sign
    {"name": "Hickory Grove","dist": 16.5}  # 3rd Price (if exists)
]

st.set_page_config(page_title="GA Express Lane Rates", page_icon="🚗")
st.title("🚗 NW Corridor Toll Rates")

def load_data():
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(IMAGE_URL, headers=headers, timeout=10)
        response.raise_for_status()
        img = Image.open(BytesIO(response.content))
        return img
    except Exception as e:
        st.error(f"Error loading image: {e}")
        return None

def process_image(img):
    # Preprocessing
    gray = img.convert('L')
    
    # ADJUSTED THRESHOLD:
    # Your image is very high contrast. We ensure we keep the white text.
    bw = gray.point(lambda x: 0 if x < 100 else 255, '1')
    
    # OCR CONFIG:
    # psm 6 = Assume a single uniform block of text. 
    # This works best for lists.
    custom_config = r'--oem 3 --psm 6'
    text = pytesseract.image_to_string(bw, config=custom_config)
    
    return text, bw

img = load_data()

if img:
    tab1, tab2 = st.tabs(["💰 Rates", "📷 Source Image"])
    
    with tab2:
        st.image(img, caption="Live Camera Feed", use_container_width=True)
    
    with tab1:
        with st.spinner('Analyzing sign text...'):
            raw_text, processed_img = process_image(img)
            
            # 1. Check for CLOSED status
            if "CLOSED" in raw_text.upper():
                st.error("Southbound Toll Lanes are Closed")
            
            else:
                # 2. Extract ALL prices found in the text
                # This regex looks for:
                # Optional $ or S or 8 (common OCR errors for $)
                # followed by digits, a dot, and 2 digits.
                # Example matches: "$0.50", "80.50", "1.10", "S1.50"
                
                price_pattern = re.compile(r'[S$8]?(\d+\.\d{2})')
                
                # Find all matches in the entire text blob
                matches = price_pattern.findall(raw_text)
                
                data = []
                
                # Loop through found prices and map them to our KNOWN locations
                for i, price_str in enumerate(matches):
                    if i < len(SIGN_ORDER):
                        try:
                            # If OCR read "80.50", the regex group captures "0.50" correctly.
                            # If it captured "80.50", we sanitize it.
                            val = float(price_str)
                            
                            # Sanity check: Tolls are rarely > $20. 
                            # If we see 80.50, it's probably $0.50 read as 80.50
                            if val > 20.0:
                                val = val - 80.0 # Rough fix for the specific "80.50" error
                                if val < 0: val = 0.50 # Fallback

                            dest = SIGN_ORDER[i]
                            per_mile = val / dest['dist']
                            
                            data.append({
                                "Destination": dest['name'],
                                "Price": f"${val:.2f}",
                                "Distance": f"{dest['dist']} mi",
                                "$/Mile": f"${per_mile:.2f}"
                            })
                        except ValueError:
                            continue

                if data:
                    df = pd.DataFrame(data)
                    st.dataframe(df, hide_index=True, use_container_width=True)
                else:
                    st.warning("Could not detect any clear prices.")
                    with st.expander("Debug Info"):
                        st.text("Raw Text found:")
                        st.code(raw_text)
                        st.text("Regex matches:")
                        st.write(matches)
