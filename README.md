https://gate-dashboard-2nbnbydr3yirypmiufc539.streamlit.app/

# GATE DA Application

This repository contains a Python application for GATE Data Analytics (DA) preparation.

## Features

- **Topic Selection**: Choose specific GATE DA topics for focused study
- **Practice Questions**: Access a database of previous year questions
- **Progress Tracking**: Monitor your performance and study progress
- **Mock Tests**: Take timed tests simulating exam conditions
- **Score Analysis**: Get detailed feedback on your test performance
- **Vision-based RAG Assistant**: Upload PDFs and ask questions about their visual content using AI vision models

## Installation

1. Clone this repository
2. Install required dependencies:
```bash
pip install -r requirements.txt
```

### PDF Processing in the RAG Assistant

The RAG Assistant uses a text-based approach to process PDFs:

1. **Text Extraction**: PyPDF2 extracts text from each page of the PDF
2. **Image Rendering**: The extracted text is rendered onto images using PIL
3. **Vision Analysis**: The rendered images are analyzed by a vision-based AI model (GPT-4o)

This approach works well for text-based PDFs but has some limitations:
- Original formatting and layout are simplified
- Images from the original PDF are not preserved
- Complex elements like tables may not be rendered accurately

## Usage

Run the application using:
```bash
python app.py
```

## File Structure

```
├── README.md
├── app.py
├── requirements.txt
├── uploads/
│   └── images/  # Stores PDF page images for the RAG Assistant
```

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.
