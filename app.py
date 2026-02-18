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
    
    # 2. Invert immediately (Make text black, background white)
    # This is critical because "Erosion" works on the BLACK part of the image.
    inverted = ImageOps.invert(gray)
    
    # 3. Threshold (High Contrast)
    # Everything darker than 100 becomes black (text), everything lighter becomes white.
    # Adjust 100 up or down if text is too thin or too thick.
    bw = inverted.point(lambda x: 0 if x < 90 else 255, '1')
    
    # 4. Resize (2x is usually enough, 3x can be too much noise)
    width, height = bw.size
    resized = bw.resize((width * 2, height * 2), resample=Image.Resampling.LANCZOS)
    
    # OCR Config
    # --psm 6 is still best for blocks of text
    # We remove the whitelist strictness slightly to let Tesseract "breathe"
    custom_config = r'--oem 3 --psm 6'
    
    text = pytesseract.image_to_string(resized, config=custom_config)
    
    return text, resized

# --- Main App Logic ---
img = load_data()

if img:
    tab1, tab2 = st.tabs(["💰 Rates", "🛠️ Debug View"])
    
    with tab1:
        if st.button("Refresh"):
            st.rerun()
            
        with st.spinner('Processing LED Sign...'):
            raw_text, processed_img = process_image(img)
            
            if "CLOSED" in raw_text.upper():
                st.error("Southbound Toll Lanes are Closed")
            else:
                # Regex Strategy:
                # 1. Look for patterns like $0.50, 0.50, .50, 1.10
                # 2. Handle common OCR errors: 'S' instead of '$', 'O' instead of '0'
                
                # Clean the text first to fix common LED read errors
                clean_text = raw_text.replace("O", "0").replace("o", "0").replace("S", "$").replace("s", "$")
                
                # Regex: Optional $ followed by digits, dot, two digits
                price_pattern = re.compile(r'\$?\s?(\d+\.\d{2})')
                matches = price_pattern.findall(clean_text)
                
                data = []
                for i, price_str in enumerate(matches):
                    if i < len(SIGN_ORDER):
                        try:
                            val = float(price_str)
                            
                            # Sanity Logic:
                            # If we see "50.50", it's likely "0.50" where the dollar sign was read as a 5.
                            # If value > 10, and it ends in the same decimals as a likely toll, suspect error.
                            if val > 15.0:
                                # Heuristic: if it's huge, assume the first digit is a misread '$'
                                str_val = str(val)
                                # Try stripping the first character if the result is a valid toll format
                                if len(str_val) >= 4: 
                                     # e.g. "50.50" -> "0.50"
                                     try:
                                         val = float(str_val[1:])
                                     except:
                                         pass
                            
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
                    st.info("Check the 'Debug View' tab.")

    with tab2:
        st.write("### What the computer sees:")
        st.image(processed_img, caption="Processed Image sent to OCR", use_container_width=True)
        st.write("### Raw Text Output:")
        st.code(raw_text)
