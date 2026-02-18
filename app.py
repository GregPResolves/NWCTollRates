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
    bw = gray.point(lambda x: 0 if x < 150 else 255, '1')
    
    # OCR
    custom_config = r'--oem 3 --psm 6'
    text = pytesseract.image_to_string(bw, config=custom_config)
    
    return text, bw

# Load and Display Image
img = load_data()

if img:
    # Create tabs
    tab1, tab2 = st.tabs(["💰 Rates", "📷 Source Image"])
    
    with tab2:
        st.image(img, caption="Live Camera Feed", use_container_width=True)
    
    with tab1:
        with st.spinner('Analyzing sign text...'):
            raw_text, processed_img = process_image(img)
            
            # --- NEW LOGIC FOR CLOSED SIGNS ---
            if "CLOSED" in raw_text.upper():
                st.error("Southbound Toll Lanes are Closed")
                st.caption("The sign currently indicates the lanes are not open for this direction.")
            
            # --- EXISTING LOGIC FOR RATES ---
            else:
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
                else:
                    # If it's not closed, but we found no data, show warning
                    st.warning("Could not read rates from the sign right now.")
                    
                    # Optional: Expander to see what the computer "saw"
                    with st.expander("See debug info"):
                        st.text("Raw OCR Output:")
                        st.code(raw_text)
                        st.image(processed_img, caption="Processed Image", width=300)

    if st.button('Refresh Data'):
        st.rerun()
