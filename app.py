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
    # 1. CROP: Focus ONLY on the right side where prices are.
    # The image is 352px wide. Prices are usually in the right 40%.
    # This removes the "Express Lanes" noise completely.
    width, height = img.size
    # Crop box: (left_x, top_y, right_x, bottom_y)
    cropped = img.crop((int(width * 0.6), 0, width, height))

    # 2. GRAYSCALE
    gray = cropped.convert('L')
    
    # 3. GLARE REDUCTION (Crucial Step)
    # MinFilter looks at a 3x3 pixel area and picks the DARKEST pixel.
    # Since text is bright and background is dark, this "eats away" the bright glow.
    # It makes the text thinner and separates the merged numbers.
    eroded = gray.filter(ImageFilter.MinFilter(3))
    
    # 4. INVERT
    # Now we have thin white text on black. Invert to Black text on White.
    inverted = ImageOps.invert(eroded)
    
    # 5. CONTRAST STRETCH
    # Make the darks darker and lights lighter without a hard binary threshold
    contrast = ImageOps.autocontrast(inverted, cutoff=10)

    # 6. RESIZE
    # Double size to give Tesseract more pixels to work with
    w, h = contrast.size
    final_img = contrast.resize((w * 2, h * 2), resample=Image.Resampling.LANCZOS)
    
    # OCR Config
    # Whitelist numbers and symbols to stop it from reading garbage
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
            # Check for "CLOSED" on the FULL image first
            full_text = pytesseract.image_to_string(img)
            
            if "CLOSED" in full_text.upper():
                st.error("Southbound Toll Lanes are Closed")
            else:
                # Process the CROPPED image for prices
                raw_text, processed_img = process_image(img)
                
                # Regex to find prices
                # Matches: $0.50, .50, 0.50
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
                            
                            # Filter out bad reads
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
                    st.info("Check the 'Debug View' tab to see the cropped image.")

    with tab2:
        st.write("### What the computer sees (Cropped & Thinned):")
        if 'processed_img' in locals():
            st.image(processed_img, caption="Processed Image sent to OCR", use_container_width=True)
        st.write("### Raw Text Output:")
        if 'raw_text' in locals():
            st.code(raw_text)
