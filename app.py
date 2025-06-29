from flask import Flask, request, render_template_string, send_from_directory
from PIL import Image
import pytesseract
import re
import os

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
RESULT_FOLDER = "results"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)

HTML_TEMPLATE = """
<!doctype html>
<html>
<head>
  <title>OCR Classified Extractor</title>
  <style>
    #loading {
      display: none;
      text-align: center;
      margin-top: 20px;
    }
    .spinner {
      border: 6px solid #f3f3f3;
      border-top: 6px solid #3498db;
      border-radius: 50%;
      width: 40px;
      height: 40px;
      animation: spin 1s linear infinite;
      margin: auto;
    }
    @keyframes spin {
      0% { transform: rotate(0deg); }
      100% { transform: rotate(360deg); }
    }
  </style>
  <script>
    function showLoading() {
      document.getElementById('form-section').style.display = 'none';
      document.getElementById('loading').style.display = 'block';
    }
  </script>
</head>
<body>
  <h2>Upload Newspaper Classified Images</h2>
  <div id="form-section">
    <form method=post enctype=multipart/form-data onsubmit="showLoading()">
      <input type=file name=image multiple required>
      <input type=submit value="Upload & Extract">
    </form>
  </div>

  <div id="loading">
    <div class="spinner"></div>
    <p>Processing images... Please wait.</p>
  </div>

  {% if listings %}
    <h3>Extracted Listings ({{ listings|length }})</h3>
    <pre style="white-space: pre-wrap; background: #f4f4f4; padding: 10px;">{{ listings_text }}</pre>

    <form method="post" action="/clean" onsubmit="showLoading()">
      <input type="hidden" name="raw_text" value="{{ listings_text | replace('"', '&#34;') | replace("'", '&#39;') }}">
      <button type="submit">Clean &quot;- &quot;</button>
    </form>

    <form method="post" action="/smart-extract" onsubmit="showLoading()">
      <input type="hidden" name="raw_text" value="{{ listings_text | replace('"', '&#34;') | replace("'", '&#39;') }}">
      <button type="submit">Smart Extract Numbers by City</button>
    </form>

    <a href="{{ download_url }}" download><button>Download Results as Text</button></a>
  {% endif %}
</body>
</html>
"""

def extract_listings_from_image(image_path):
    image = Image.open(image_path)
    raw_text = pytesseract.image_to_string(image)

    lines = [line.strip() for line in raw_text.split('\n') if line.strip()]
    listings = []
    current_listing = []

    for line in lines:
        current_listing.append(line)

        if re.search(r'\(CL\d{5,}\)', line) or re.search(r'\b\d{5}[-\s]?\d{5}\b', line):
            listings.append(" ".join(current_listing))
            current_listing = []

    if current_listing:
        listings.append(" ".join(current_listing))

    return listings

@app.route('/', methods=['GET', 'POST'])
def index():
    listings = []
    listings_text = ''
    download_url = ''

    if request.method == 'POST':
        uploaded_files = request.files.getlist('image')
        all_listings = []

        for uploaded_file in uploaded_files:
            if uploaded_file and uploaded_file.filename != '':
                filename = uploaded_file.filename
                filepath = os.path.join(UPLOAD_FOLDER, filename)
                uploaded_file.save(filepath)

                file_listings = extract_listings_from_image(filepath)
                all_listings.extend(file_listings)

        listings = all_listings
        listings_text = '\n'.join(listings)

        result_txt_path = os.path.join(RESULT_FOLDER, "multi_uploaded_results.txt")
        with open(result_txt_path, 'w', encoding='utf-8') as f:
            f.write(listings_text)

        download_url = "/download/multi_uploaded_results.txt"

    return render_template_string(HTML_TEMPLATE, listings=listings, listings_text=listings_text, download_url=download_url)

@app.route('/clean', methods=['POST'])
def clean_text():
    raw_text = request.form['raw_text']
    cleaned_text = raw_text.replace('- ', '')

    result_txt_path = os.path.join(RESULT_FOLDER, "cleaned_results.txt")
    with open(result_txt_path, 'w', encoding='utf-8') as f:
        f.write(cleaned_text)

    listings = cleaned_text.split('\n')
    download_url = "/download/cleaned_results.txt"

    return render_template_string(HTML_TEMPLATE, listings=listings, listings_text=cleaned_text, download_url=download_url)

@app.route('/smart-extract', methods=['POST'])
def smart_extract():
    raw_text = request.form['raw_text']
    lines = raw_text.split('\n')
    phone_pattern = re.compile(r'\b\d{5}[-]?\d{5}\b')

    city_data = {
        'Chandigarh': [],
        'Mohali': [],
        'Panchkula': []
    }

    for line in lines:
        lowered = line.lower()
        numbers = phone_pattern.findall(line)
        numbers = [num.replace('-', '') for num in numbers]  # Normalize by removing hyphen

        if not numbers:
            continue

        if 'chandigarh' in lowered:
            city_data['Chandigarh'].extend(numbers)
        elif 'mohali' in lowered:
            city_data['Mohali'].extend(numbers)
        elif 'panchkula' in lowered:
            city_data['Panchkula'].extend(numbers)

    result_lines = []
    for city, numbers in city_data.items():
        result_lines.append(f"{city}:")
        if numbers:
            result_lines.extend(numbers)
        else:
            result_lines.append("No numbers found.")
        result_lines.append("")  # blank line between cities

    result_text = '\n'.join(result_lines)
    result_txt_path = os.path.join(RESULT_FOLDER, "smart_city_numbers.txt")
    with open(result_txt_path, 'w', encoding='utf-8') as f:
        f.write(result_text)

    listings = result_lines
    download_url = "/download/smart_city_numbers.txt"

    return render_template_string(HTML_TEMPLATE, listings=listings, listings_text=result_text, download_url=download_url)

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(RESULT_FOLDER, filename, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
