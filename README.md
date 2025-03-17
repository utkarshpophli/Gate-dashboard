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

### Additional Requirements for Vision-based RAG Assistant

The RAG Assistant uses two methods to process PDFs:

#### Primary Method (Best Quality)
- **pdf2image**: For converting PDFs to images
- **Poppler**: A dependency for pdf2image
  - On Windows: 
    - Download from [poppler-windows releases](https://github.com/oschwartz10612/poppler-windows/releases/)
    - Extract to a folder (e.g., `C:\poppler`)
    - Add the bin directory to your system PATH or specify the path in the application

  - On macOS: `brew install poppler`
  - On Linux: `apt-get install poppler-utils`

#### Fallback Method (If Poppler is unavailable)
If Poppler is not available, the application will use a basic fallback method:

- **PyPDF2 + PIL**: Extracts text from PDF and renders it to images
  - This method has limited visual quality but works without external dependencies
  - Text formatting and layout will be simplified
  - Images and complex formatting in the PDF will not be preserved

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
