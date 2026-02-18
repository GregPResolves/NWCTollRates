import streamlit as st
import requests
from PIL import Image, ImageOps, ImageFilter
import pytesseract
import re
from io import BytesIO
import pandas as pd

# --- Configuration ---
IMAGE_URL = "https://srtaivedds.com/Images/Cameras/75B-002.0-CMS-CAM01-00001.jpg"

# KNOWN ORDER (Top to Bottom)
SIGN_ORDER = [
    {"name": "Roswell Rd",   "dist": 6.0},  
    {"name": "Big Shanty",   "dist": 12.0}, 
    {"name": "Hickory Grove","dist": 16.5}
]

st.set_page_config(page_title="GA Express Lane Rates", page_icon="🚗")
st.title("🚗 NW Corridor Toll Rates")

def load_data():
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        # Add random param to prevent caching
        response = requests.get(IMAGE_URL, headers=headers, timeout=10)
        response.raise_for_status()
        img = Image.open(BytesIO(response.content))
        return img
    except Exception as e:
        st.error(f"Error loading image: {e}")
        return None

def process_image(img):
    # 1. Convert to Greyscale
    gray = img.convert('L')
    
    # 2. RESIZE: Blow it up 3x. This helps Tesseract distinguish letters from background noise.
    # High-quality resampling (LANCZOS) helps keep edges sharp.
    width, height = gray.size
    gray = gray.resize((width * 3, height * 3), resample=Image.Resampling.LANCZOS)
    
    # 3. BLUR: Use a slight blur to merge the LED dots together
    # Radius 2 usually connects the dots of an LED sign
    blurred = gray.filter(ImageFilter.GaussianBlur(radius=2))
    
    # 4. THRESHOLD: Make it strictly Black and White
    # We tweak the 150 value. Lower = more white, Higher = more black.
    bw = blurred.point(lambda x: 0 if x < 140 else 255, '1')
    
    # 5. INVERT: Tesseract reads BLACK text on WHITE background better
    # We need to convert back to 'L' mode to invert, then back to '1'
    inverted = ImageOps.invert(bw.convert('L'))
    
    # OCR Config:
    # --psm 6: Assume a single uniform block of text
    # -c tessedit_char_whitelist=0123456789.$CLOSED : Only look for these chars
    custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789.$CLOSED'
    
    text = pytesseract.image_to_string(inverted, config=custom_config)
    
    return text, inverted

# --- Main App Logic ---
img = load_data()

if img:
    tab1, tab2 = st.tabs(["💰 Rates", "🛠️ Debug View"])
    
    with tab1:
        if st.button("Refresh"):
            st.rerun()
            
        with st.spinner('Processing LED Sign...'):
            raw_text, processed_img = process_image(img)
            
            # 1. Check CLOSED
            if "CLOSED" in raw_text.upper():
                st.error("Southbound Toll Lanes are Closed")
            
            else:
                # 2. Find Prices
                # Look for numbers that look like prices (e.g., 0.50, 1.10)
                # We allow 1 or 2 digits before the dot, and exactly 2 after.
                price_pattern = re.compile(r'(\d{1,2}\.\d{2})')
                matches = price_pattern.findall(raw_text)
                
                data = []
                for i, price_str in enumerate(matches):
                    if i < len(SIGN_ORDER):
                        try:
                            val = float(price_str)
                            # Sanity Check: If price > $20, it's likely a read error (e.g. 50.50 instead of 0.50)
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
                    st.success(f"Found {len(data)} rates")
                    df = pd.DataFrame(data)
                    st.dataframe(df, hide_index=True, use_container_width=True)
                else:
                    st.warning("Could not read numbers clearly.")
                    st.info("Check the 'Debug View' tab to see what the computer is seeing.")

    with tab2:
        st.write("### What the computer sees:")
        st.write("We resized, blurred, and inverted the image to make dots look like lines.")
        st.image(processed_img, caption="Processed Image sent to OCR", use_container_width=True)
        st.write("### Raw Text Output:")
        st.code(raw_text)
