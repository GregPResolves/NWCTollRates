import streamlit as st
import requests
from PIL import Image, ImageOps, ImageFilter
import pytesseract
import re
from io import BytesIO
import pandas as pd

# --- Configuration ---
IMAGE_URL = "https://srtaivedds.com/Images/Cameras/75B-002.0-CMS-CAM01-00001.jpg"

# ACTUAL DISTANCES (Southbound from Barrett Pkwy Entrance)
# 1. Barrett -> Roswell Rd (~5.5 miles)
# 2. Barrett -> I-285 (~11.0 miles)
# 3. Terrell Mill is roughly 9.0 miles from Barrett (between Roswell and 285)

# We map the OCR results to the VISIBLE lines on the sign.
# The sign usually shows [Roswell Rd] (Top) and [I-285] (Bottom)
SIGN_LOCATIONS = [
    {"name": "Roswell Rd", "dist": 5.5},  # First price detected
    {"name": "I-285",      "dist": 11.0}  # Second price detected
]

# Hidden destination we want to calculate
TERRELL_MILL_DIST = 9.0

st.set_page_config(page_title="GA Express Lane Rates", page_icon="🚗", layout="wide")
st.title("🚗 NW Corridor Toll Rates (Barrett Pkwy)")

# --- SIDEBAR ---
st.sidebar.header("🔧 Calibration")
threshold_val = st.sidebar.slider("Threshold", 0, 255, 160)
crop_val = st.sidebar.slider("Crop Left %", 0, 80, 55)
resize_factor = st.sidebar.selectbox("Resize Factor", [1, 2, 3], index=2)
invert_img = st.sidebar.checkbox("Invert Colors", value=True)

def load_data():
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(IMAGE_URL, headers=headers, timeout=5)
        response.raise_for_status()
        img = Image.open(BytesIO(response.content))
        return img
    except Exception as e:
        st.error(f"Error loading image: {e}")
        return None

def process_image(img, thresh, crop_pct, resize, do_invert):
    w, h = img.size
    left = int(w * (crop_pct / 100))
    cropped = img.crop((left, 0, w, h))
    gray = cropped.convert('L')
    w_new, h_new = gray.size
    resized = gray.resize((w_new * resize, h_new * resize), resample=Image.Resampling.BICUBIC)
    binary = resized.point(lambda x: 255 if x > thresh else 0, '1')
    
    if do_invert:
        final_img = ImageOps.invert(binary.convert('L'))
    else:
        final_img = binary.convert('L')
    
    custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=$0123456789.'
    text = pytesseract.image_to_string(final_img, config=custom_config)
    
    return text, final_img

# --- Main Logic ---
if st.button("🔄 Refresh Camera"):
    st.rerun()

img = load_data()

if img:
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("💰 Live Rates")
        with st.spinner('Calculating...'):
            full_text_check = pytesseract.image_to_string(img)
            
            if "CLOSED" in full_text_check.upper():
                st.error("⛔ Southbound Toll Lanes are Closed")
            else:
                raw_text, processed_img = process_image(img, threshold_val, crop_val, resize_factor, invert_img)
                
                # Regex for prices
                matches = re.findall(r'\$?\s?(\d*\.\d{2})', raw_text)
                
                data = []
                avg_rate_per_mile = 0.10 # fallback default
                
                # 1. Process Visible Signs
                for i, price_str in enumerate(matches):
                    if i < len(SIGN_LOCATIONS):
                        try:
                            if price_str.startswith('.'): price_str = "0" + price_str
                            val = float(price_str)
                            if val > 20.0: continue 

                            dest = SIGN_LOCATIONS[i]
                            per_mile = val / dest['dist']
                            
                            # If this is the I-285 price (longest trip), use it as the "True Rate"
                            if dest['name'] == "I-285":
                                avg_rate_per_mile = per_mile

                            data.append({
                                "Destination": dest['name'],
                                "Price": f"${val:.2f}",
                                "$/Mile": f"${per_mile:.2f}"
                            })
                        except ValueError:
                            continue
                
                # 2. Calculate Hidden Destination (Terrell Mill)
                # Only add if we found at least one price to base the rate on
                if data:
                    terrell_price = avg_rate_per_mile * TERRELL_MILL_DIST
                    # Insert it in the middle (Index 1)
                    data.insert(1, {
                        "Destination": "Terrell Mill (Calc)",
                        "Price": f"${terrell_price:.2f}",
                        "$/Mile": f"${avg_rate_per_mile:.2f}"
                    })

                    df = pd.DataFrame(data)
                    st.dataframe(df, hide_index=True, use_container_width=True)
                else:
                    st.warning("No rates detected.")

    with col2:
        st.subheader("👁️ Debug View")
        if 'processed_img' in locals():
            st.image(processed_img, caption=f"Debug Feed", use_container_width=True)
            st.code(raw_text)
