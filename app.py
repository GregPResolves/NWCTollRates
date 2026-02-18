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
    # 1. CROP: Focus on the right side.
    # We use 0.5 (50%) to be safe. 
    # This keeps the numbers but cuts out the "Destination" text.
    w, h = img.size
    cropped = img.crop((int(w * 0.5), 0, w, h))

    # 2. GRAYSCALE
    gray = cropped.convert('L')
    
    # 3. HIGH THRESHOLD (The Anti-Glow Step)
    # LED signs have a "halo" or glow that confuses the computer.
    # By setting the threshold HIGH (200), we only keep the bright center of the LED dots.
    # 0 = Black, 255 = White.
    binary = gray.point(lambda x: 255 if x > 200 else 0, '1')
    
    # 4. DILATION (The "Connect-the-Dots" Step)
    # MaxFilter looks at neighbors and picks the brightest one.
    # This expands the white dots until they touch, forming solid letters.
    # Size 3 is usually perfect for this.
    thickened = binary.filter(ImageFilter.MaxFilter(3))
    
    # 5. INVERT
    # Tesseract needs Black text on White background.
    inverted = ImageOps.invert(thickened.convert('L'))
    
    # 6. RESIZE
    # Blow it up 2x so Tesseract sees the details.
    final_img = inverted.resize((w * 2, h * 2), resample=Image.Resampling.NEAREST)
    
    # OCR Config
    # We restrict the character set strictly to money-related characters
    custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=$0123456789.'
    
    text = pytesseract.image_to_string(final_img, config=custom_config)
    
    return text, final_img

# --- Main App Logic ---
img = load_data()

if img:
    tab1, tab2 = st.tabs(["💰 Rates", "🛠️ Debug View"])
    
    with tab1:
        if st.button("Refresh"):
            st.rerun()
            
        with st.spinner('Processing LED Sign...'):
            # Check CLOSED status on the original full image
            full_text = pytesseract.image_to_string(img)
            
            if "CLOSED" in full_text.upper():
                st.error("Southbound Toll Lanes are Closed")
            else:
                raw_text, processed_img = process_image(img)
                
                # Regex matches: $0.50, .50, 0.50
                price_pattern = re.compile(r'\$?\s?(\d*\.\d{2})')
                matches = price_pattern.findall(raw_text)
                
                data = []
                for i, price_str in enumerate(matches):
                    if i < len(SIGN_ORDER):
                        try:
                            # Fix empty leading digits (e.g. ".50" -> "0.50")
                            if price_str.startswith('.'):
                                price_str = "0" + price_str
                                
                            val = float(price_str)
                            
                            # Filter out bad reads (Tolls over $20 are unlikely errors)
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
                    st.info("Check the 'Debug View' tab.")

    with tab2:
        st.write("### What the computer sees:")
        st.write("We are keeping only the brightest pixels (dots) and then expanding them to touch.")
        if 'processed_img' in locals():
            st.image(processed_img, caption="Processed Image sent to OCR", use_container_width=True)
        st.write("### Raw Text Output:")
        if 'raw_text' in locals():
            st.code(raw_text)
