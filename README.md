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

The RAG Assistant now supports two AI models for analyzing PDF content:

#### Llama-3.2-90B-Vision-Instruct (Recommended for Scanned PDFs)
- Powerful OCR capabilities built into the model
- Better at handling scanned documents and handwritten text
- Can understand complex layouts and visual elements

#### GPT-4o (Alternative Option)
- Good for text-based PDFs and general visual analysis
- Works well with digital PDFs that have selectable text

The application attempts to process PDFs in two ways:
1. **High-Quality Image Conversion**: Using pdf2image to create high-resolution images (300 DPI)
2. **Fallback Text Rendering**: If pdf2image is unavailable, text is extracted and rendered onto images

For best results with scanned documents:
- Select the Llama-3.2-90B-Vision-Instruct model
- The higher resolution images (300 DPI) improve OCR accuracy

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
