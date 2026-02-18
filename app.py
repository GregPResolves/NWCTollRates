import streamlit as st
import requests
from PIL import Image, ImageOps, ImageFilter
import pytesseract
import re
from io import BytesIO
import pandas as pd

# --- Configuration ---
IMAGE_URL = "https://srtaivedds.com/Images/Cameras/75B-002.0-CMS-CAM01-00001.jpg"

SIGN_ORDER = [
    {"name": "Roswell Rd",   "dist": 6.0},  
    {"name": "Big Shanty",   "dist": 12.0}, 
    {"name": "Hickory Grove","dist": 16.5}
]

st.set_page_config(page_title="GA Express Lane Rates", page_icon="🚗", layout="wide")
st.title("🚗 NW Corridor Toll Rates")

# --- SIDEBAR CONTROLS ---
st.sidebar.header("🔧 Calibration")
st.sidebar.write("Tweak these if the sign is unreadable.")

# Default to 160 (Day/General), but allow user to slide it
threshold_val = st.sidebar.slider("Threshold (Dark vs Light)", 0, 255, 160, help="Lower = Thicker text. Higher = Thinner text.")
crop_val = st.sidebar.slider("Crop Left %", 0, 80, 55, help="How much of the left side to cut off.")
resize_factor = st.sidebar.selectbox("Resize Factor", [1, 2, 3], index=2, help="3x is smoother, 1x is raw.")
invert_img = st.sidebar.checkbox("Invert Colors", value=True, help="Tesseract needs Black Text on White Background.")

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
    # 1. CROP
    w, h = img.size
    # Convert percentage to pixel value
    left = int(w * (crop_pct / 100))
    cropped = img.crop((left, 0, w, h))

    # 2. GRAYSCALE
    gray = cropped.convert('L')
    
    # 3. RESIZE (Bicubic for smoothness)
    w_new, h_new = gray.size
    resized = gray.resize((w_new * resize, h_new * resize), resample=Image.Resampling.BICUBIC)

    # 4. THRESHOLD (Dynamic via Slider)
    # If pixel > threshold, make it White (255), else Black (0)
    binary = resized.point(lambda x: 255 if x > thresh else 0, '1')
    
    # 5. INVERT (Dynamic Checkbox)
    if do_invert:
        final_img = ImageOps.invert(binary.convert('L'))
    else:
        final_img = binary.convert('L')
    
    # OCR Config
    # Restrict to money characters to reduce noise
    custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=$0123456789.'
    
    text = pytesseract.image_to_string(final_img, config=custom_config)
    
    return text, final_img

# --- Main App Logic ---
if st.button("🔄 Refresh Camera"):
    st.rerun()

img = load_data()

if img:
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("💰 Live Rates")
        with st.spinner('Processing...'):
            # Check CLOSED status on original image
            full_text_check = pytesseract.image_to_string(img)
            
            if "CLOSED" in full_text_check.upper():
                st.error("⛔ Southbound Toll Lanes are Closed")
            else:
                # Run the processor with SLIDER values
                raw_text, processed_img = process_image(img, threshold_val, crop_val, resize_factor, invert_img)
                
                # Regex and Parsing
                price_pattern = re.compile(r'\$?\s?(\d*\.\d{2})')
                matches = price_pattern.findall(raw_text)
                
                data = []
                for i, price_str in enumerate(matches):
                    if i < len(SIGN_ORDER):
                        try:
                            if price_str.startswith('.'): price_str = "0" + price_str
                            val = float(price_str)
                            if val > 20.0: continue 

                            dest = SIGN_ORDER[i]
                            per_mile = val / dest['dist']
                            
                            data.append({
                                "Destination": dest['name'],
                                "Price": f"${val:.2f}",
                                "$/Mile": f"${per_mile:.2f}"
                            })
                        except ValueError:
                            continue
                
                if data:
                    df = pd.DataFrame(data)
                    st.dataframe(df, hide_index=True, use_container_width=True)
                else:
                    st.warning("No rates detected.")
                    st.caption("Try adjusting the Threshold slider in the sidebar.")

    with col2:
        st.subheader("👁️ Debug View")
        # Show what the computer sees so you can tune the slider
        if 'processed_img' in locals():
            st.image(processed_img, caption=f"Threshold: {threshold_val} | Crop: {crop_val}%", use_container_width=True)
            st.text("Raw OCR Output:")
            st.code(raw_text)
        
        with st.expander("View Original Camera Feed"):
            st.image(img, use_container_width=True)
