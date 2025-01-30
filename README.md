# SEO Blog Meta Analyzer

This application analyzes blog content from a sitemap URL using DeepSek's API to generate SEO-optimized summaries. The results are exported to a spreadsheet containing blog titles, URLs, and optimized summaries.

## Features
- Sitemap URL processing
- Blog content extraction
- Content analysis using DeepSek's API
- SEO-optimized summary generation
- Excel export functionality

## Setup

### Prerequisites
- Python 3.8+
- Node.js 16+
- npm or yarn

### Backend Setup
1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file and add your DeepSek API key:
```
DEEPSEK_API_KEY=your_api_key_here
```

### Frontend Setup
1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Start the development server:
```bash
npm start
```

## Usage
1. Start the backend server:
```bash
python backend/main.py
```

2. Open your browser and navigate to `http://localhost:3000`
3. Enter your sitemap URL
4. Click analyze to process the blogs and generate summaries
5. Download the resulting spreadsheet

## Contributing
1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request 