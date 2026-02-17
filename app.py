import streamlit as st
import requests
from PIL import Image
import pytesseract
import re
from io import BytesIO
import pandas as pd

# --- Configuration ---
# Camera URL
IMAGE_URL = "https://srtaivedds.com/Images/Cameras/75B-002.0-CMS-CAM01-00001.jpg"

# Distances from Akers Mill (Start of NWC) to exits
DISTANCES_MILES = {
    "TERRELL": 2.5,
    "ROSWELL": 6.0,
    "BIG SHANTY": 12.0,
    "HICKORY": 16.5,
    "SIXES": 20.0,
    "575": 10.0, 
}

# Set page title
st.set_page_config(page_title="GA Express Lane Rates", page_icon="🚗")

st.title("🚗 NW Corridor Toll Rates")
st.write("Live rates extracted from the Akers Mill entrance sign.")

def load_data():
    try:
        # 1. Fetch Image
        headers = {'User-Agent': 'Mozilla/5.0'}
        # Add a timestamp to URL to prevent caching if needed, usually requests doesn't cache by default
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
    # Simple thresholding to isolate bright text
    bw = gray.point(lambda x: 0 if x < 130 else 255, '1')
    
    # OCR
    # psm 6 assumes a single uniform block of text
    custom_config = r'--oem 3 --psm 6'
    text = pytesseract.image_to_string(bw, config=custom_config)
    
    return text, bw

# Load and Display Image
img = load_data()

if img:
    # Create tabs for clean view
    tab1, tab2 = st.tabs(["💰 Rates", "📷 Source Image"])
    
    with tab2:
        st.image(img, caption="Live Camera Feed", use_container_width=True)
    
    with tab1:
        with st.spinner('Analyzing sign text...'):
            raw_text, processed_img = process_image(img)
            
            # Parsing Logic
            lines = raw_text.split('\n')
            data = []
            price_pattern = re.compile(r'\$?\s?(\d+\.\d{2})')

            for line in lines:
                line_upper = line.upper().strip()
                for key, miles in DISTANCES_MILES.items():
                    if key in line_upper:
                        price_match = price_pattern.search(line)
                        if price_match:
                            price = float(price_match.group(1))
                            per_mile = price / miles if miles > 0 else 0
                            data.append({
                                "Destination": key,
                                "Price": f"${price:.2f}",
                                "Distance": f"{miles} mi",
                                "$/Mile": f"${per_mile:.2f}"
                            })
                        break
            
            if data:
                df = pd.DataFrame(data)
                st.dataframe(df, hide_index=True, use_container_width=True)
                
                # Highlight best value (optional)
                # st.success(f"Current variable rate is roughly {data[0]['$/Mile']} per mile.")
            else:
                st.warning("Could not read rates from the sign right now.")
                st.text("Raw OCR Output for debugging:")
                st.code(raw_text)
                st.image(processed_img, caption="Processed Image for OCR", width=300)

    if st.button('Refresh Data'):
        st.rerun()