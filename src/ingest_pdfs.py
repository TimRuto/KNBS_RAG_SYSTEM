"""
Ingest all PDFs in src/data/ into the RAG system.
Usage:
    cd RAG-Skeleton
    pip install pdfplumber PyPDF2   # if not already installed
    python src/ingest_pdfs.py

This script will:
 - Use `PDFProcessor` to extract text and metadata from PDFs in `src/data/`
 - Initialize the RAGAssistant and add the extracted documents to the vector DB
 - Print a short summary of processed files and resulting chunk count
"""
import os
import sys
from pathlib import Path

# Ensure src is on path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from pdf_processor import PDFProcessor
from app import RAGAssistant

DATA_DIR = Path(__file__).resolve().parent / 'data'


def main():
    print("\nStarting PDF ingestion helper...")

    if not DATA_DIR.exists():
        print(f"Data directory not found: {DATA_DIR}")
        return

    # Find pdf files
    pdf_files = [str(p) for p in DATA_DIR.glob('**/*.pdf')]
    if not pdf_files:
        print(f"No PDF files found in {DATA_DIR}. Place KNBS PDFs there and re-run.")
        return

    print(f"Found {len(pdf_files)} PDF(s) to process:")
    for p in pdf_files:
        print(" -", os.path.basename(p))

    # Process PDFs
    processor = PDFProcessor()
    docs = processor.process_directory(str(DATA_DIR))

    if not docs:
        print("No documents extracted from PDFs.")
        return

    # Initialize assistant and ingest
    assistant = RAGAssistant()
    assistant.add_documents(docs)

    print("\nIngestion complete.")
    print(f"Processed documents: {len(docs)}")
    print(f"Vector DB collection now has: {assistant.vector_db.collection.count()} chunks")


if __name__ == '__main__':
    main()
