import streamlit as st
import os
import tempfile
import pandas as pd
import fitz  # PyMuPDF
import base64
import requests
import re

# Function to convert PDF to JPEG
def convert_pdf_to_jpeg(pdf_path, output_folder):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    doc = fitz.open(pdf_path)
    if doc.is_encrypted:
        st.error("PDF is encrypted. Unable to convert to images.")
        return
    for page_num in range(doc.page_count):
        page = doc[page_num]
        zoom = 2  # Increase for higher resolution
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        image_path = os.path.join(output_folder, f"page_{page_num + 1}.jpg")
        pix.save(image_path)
        # st.write(f"Page {page_num + 1} converted to JPEG image: {image_path}")

def create_prompt(column_headers):
    prompt = "Please provide the following information from these handwritten forms in a key-value format. For each item, write the key (column header), followed by a colon, and then the value. TRY VERY HARD TO READ EVERYTHING AS IS, INFER WHERE NECESSARY! If any information is obviously missing or utterly unreadable, as a last resort, write 'N/A'. IT IS CRITICAL TO USE THE EXACT SAME HEADERS AS ARE IN THE LIST I JUST SHOWED YOU AS KEYS IN YOUR OUTPUT.\n\n"
    for header in column_headers:
        prompt += f"- {header}: \n"
    return prompt

# Function to encode the image in JPEG
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        encoded_image = base64.b64encode(image_file.read()).decode('utf-8')
    return f"data:image/jpeg;base64,{encoded_image}"

# Function to analyze two images with GPT-4
def analyze_images_with_gpt4(image_path1, image_path2, api_key, column_headers):
    base64_image1 = encode_image(image_path1)
    base64_image2 = encode_image(image_path2)
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    prompt = create_prompt(column_headers)
    payload = {
        "model": "gpt-4-vision-preview",
        "temperature": 0.2,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": base64_image1}},
                    {"type": "image_url", "image_url": {"url": base64_image2}}
                ]
            }
        ],
        "max_tokens": 1000,
    }
    response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
    return response.json()

# Function to parse GPT-4 response
def parse_gpt4_response(response_data, column_headers):
    extracted_data = {header: 'N/A' for header in column_headers}
    if 'choices' in response_data and len(response_data['choices']) > 0:
        content = response_data['choices'][0].get('message', {}).get('content', '')
        header_pattern = "|".join(re.escape(header) for header in column_headers)
        pattern = re.compile(f"({header_pattern}):\s*(.*?)(?=(\n{header_pattern}:\s|$))", re.DOTALL)
        for match in pattern.finditer(content):
            header = match.group(1)
            value = match.group(2).strip()
            if header in column_headers:
                extracted_data[header] = ' '.join(value.split())
    return extracted_data

# Main function for Streamlit app
def main():
    st.title("Beckley, PDFs of feedback --> CSV")
    uploaded_file = st.file_uploader("Upload a PDF", type="pdf")
    api_key = st.secrets['API_KEY']
    # Column headers from the CSV file
    column_headers = [
    'First Name',
    'Last Name',
    'NPS [AVG=10] [RATING]',
    'The retreat application & registration process was clear and easy.',
    'Retreat logistics communications, emails, checklists and travel support were clear, timely, and helpful.',
    'Please recommend ways we can improve our application, registration, logistics, and travel support:',
    'The 4-week Preparation Program adequately prepared me for my retreat experience.',
    'The 1:1 pre session was valuable and informative.',
    'The Beckley Retreats app was valuable and informative.',
    'The virtual group prep sessions were valuable and informative.',
    'Please provide any other feedback on the preparation experience, positive or constructive:',
    'Beckley Retreats aims to balance and blend modern science with spiritual mysticism. In your personal experience during the retreat, was the program too scientific? Too mystical/spiritual? Or just right?',
    'The retreat activities and facilitators met me where I am in my spiritual/personal discovery journey.',
    'I am satisfied with my stay, the cuisine, and the accommodations at the retreat center.',
    'I felt physically, emotionally and psychologically comfortable and safe during the retreat.',
    'Program facilitators were skilled, professional, and supportive.',
    'I felt included, a sense of belonging, and attention to diversity and cultural sensitivity during the retreat.',
    'Please recommend ways we can improve the retreat experience and facilitation.',
    'I perceive my physical wellbeing to have improved since before the retreat.',
    'I perceive my mental-emotional wellbeing to have improved since before the retreat',
    'I perceive my spiritual connection to have improved since before the retreat.',
    'I perceive my connection to others to have improved since before the retreat.',
    'I perceive my connection to nature to have improved since before the retreat.',
    'Additional Feedback'
    ]
    if uploaded_file and st.button('Process File'):
        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = os.path.join(temp_dir, "uploaded.pdf")
            with open(pdf_path, "wb") as f:
                f.write(uploaded_file.read())
            convert_pdf_to_jpeg(pdf_path, temp_dir)

            # Indicate completion of JPEG conversion
            st.success("PDF conversion to JPEG completed.")

            # Show spinner during the processing of images
            with st.spinner("Processing the images. This could take a few minutes. Please do not close the tab."):
                all_data = []
                image_files = sorted([f for f in os.listdir(temp_dir) if f.endswith('.jpg')])
                for i in range(0, len(image_files), 2):
                    if i + 1 < len(image_files):
                        image_path1 = os.path.join(temp_dir, image_files[i])
                        image_path2 = os.path.join(temp_dir, image_files[i + 1])
                        response_data = analyze_images_with_gpt4(image_path1, image_path2, api_key, column_headers)
                        person_data = parse_gpt4_response(response_data, column_headers)
                        all_data.append(person_data)

            df = pd.DataFrame(all_data)
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("Download CSV", csv, "processed_data.csv", "text/csv")

if __name__ == "__main__":
    main()