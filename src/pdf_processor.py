"""
PDF Processor Module for KNBS RAG System
Handles extraction of text and metadata from PDF documents
while preserving important structural information for statistical data.
"""

import os
import re
from typing import List, Dict, Any, Optional
from pathlib import Path

try:
    import PyPDF2
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False
    print("Warning: PyPDF2 not installed. PDF processing will have limited functionality.")

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False
    print("Warning: pdfplumber not installed. Advanced PDF processing unavailable.")


class PDFProcessor:
    """
    Processes PDF files to extract text and metadata for RAG ingestion.
    Supports multiple extraction methods with fallbacks.
    """

    def __init__(self, preserve_structure: bool = True):
        """
        Initialize PDF processor.
        
        Args:
            preserve_structure: If True, attempt to preserve document structure
        """
        self.preserve_structure = preserve_structure
        self.supported_formats = [".pdf", ".txt"]

    def process_pdf_file(
        self, 
        file_path: str, 
        extract_metadata: bool = True
    ) -> Dict[str, Any]:
        """
        Process a single PDF file and extract content and metadata.
        
        Args:
            file_path: Path to the PDF file
            extract_metadata: Whether to extract metadata from the document
            
        Returns:
            Dictionary containing 'content' and 'metadata' keys
        """
        file_path = str(file_path)
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        file_ext = os.path.splitext(file_path)[1].lower()
        filename = os.path.basename(file_path)
        
        # Handle text files (pass-through)
        if file_ext == ".txt":
            return self._process_text_file(file_path, filename)
        
        # Handle PDF files
        if file_ext == ".pdf":
            return self._process_pdf(file_path, filename, extract_metadata)
        
        raise ValueError(f"Unsupported file format: {file_ext}")

    def _process_text_file(self, file_path: str, filename: str) -> Dict[str, Any]:
        """
        Process a text file (for compatibility).
        
        Args:
            file_path: Path to the text file
            filename: Name of the file
            
        Returns:
            Dictionary with content and metadata
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract metadata from content
        metadata = self._extract_text_metadata(content, filename)
        
        return {
            "content": content,
            "metadata": metadata
        }

    def _process_pdf(
        self, 
        file_path: str, 
        filename: str,
        extract_metadata: bool = True
    ) -> Dict[str, Any]:
        """
        Process a PDF file using available libraries.
        
        Args:
            file_path: Path to PDF file
            filename: Name of the file
            extract_metadata: Whether to extract metadata
            
        Returns:
            Dictionary with extracted content and metadata
        """
        content = None
        metadata = {}
        
        # Try pdfplumber first (better for tables and structure)
        if PDFPLUMBER_AVAILABLE:
            try:
                content, metadata = self._extract_with_pdfplumber(file_path)
            except Exception as e:
                print(f"pdfplumber extraction failed for {filename}: {e}")
                content = None
        
        # Fallback to PyPDF2
        if content is None and PYPDF2_AVAILABLE:
            try:
                content, pdf_metadata = self._extract_with_pypdf2(file_path)
                metadata = pdf_metadata
            except Exception as e:
                print(f"PyPDF2 extraction failed for {filename}: {e}")
                content = None
        
        # If all extraction methods fail
        if content is None:
            raise RuntimeError(
                f"Could not extract text from {filename}. "
                f"Ensure PyPDF2 or pdfplumber is installed: "
                f"pip install PyPDF2 pdfplumber"
            )
        
        # Extract additional metadata from content if requested
        if extract_metadata:
            content_metadata = self._extract_text_metadata(content, filename)
            metadata.update(content_metadata)
        
        # Add filename and file size to metadata
        metadata["source"] = filename
        metadata["file_size_kb"] = os.path.getsize(file_path) / 1024
        metadata["total_pages"] = metadata.get("total_pages", 
                                               self._count_pages(file_path))
        
        return {
            "content": content,
            "metadata": metadata
        }

    def _extract_with_pdfplumber(self, file_path: str) -> tuple:
        """
        Extract text from PDF using pdfplumber (preserves structure better).
        Handles malformed PDFs gracefully.
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            Tuple of (content, metadata)
        """
        content_parts = []
        metadata = {}
        
        try:
            with pdfplumber.open(file_path) as pdf:
                metadata["total_pages"] = len(pdf.pages)
                
                # Extract PDF-level metadata
                if pdf.metadata:
                    metadata["pdf_title"] = pdf.metadata.get("Title", "")
                    metadata["pdf_author"] = pdf.metadata.get("Author", "")
                    metadata["pdf_subject"] = pdf.metadata.get("Subject", "")
                    metadata["pdf_creator"] = pdf.metadata.get("Creator", "")
                
                # Extract text from each page
                for page_num, page in enumerate(pdf.pages, 1):
                    try:
                        # Try to extract tables first (important for statistical data)
                        tables = page.extract_tables()
                        
                        if tables:
                            for table in tables:
                                try:
                                    # Convert table to text format
                                    table_text = self._table_to_text(table)
                                    content_parts.append(table_text)
                                except Exception as e:
                                    # Skip problematic tables, continue with text
                                    pass
                        
                        # Extract regular text
                        text = page.extract_text()
                        if text:
                            content_parts.append(text)
                        
                        # Add page break indicator for structure preservation
                        content_parts.append(f"\n--- Page {page_num} ---\n")
                    
                    except Exception as e:
                        # Skip problematic pages but continue processing
                        print(f"  Warning: Could not extract page {page_num}: {str(e)[:60]}")
                        content_parts.append(f"\n--- Page {page_num} (extraction error) ---\n")
                        continue
        
        except Exception as e:
            # If PDF opening fails, raise to trigger fallback
            raise RuntimeError(f"pdfplumber failed to open PDF: {e}")
        
        content = "\n".join(content_parts)
        return content, metadata

    def _extract_with_pypdf2(self, file_path: str) -> tuple:
        """
        Extract text from PDF using PyPDF2 (fallback method).
        Handles malformed PDFs gracefully.
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            Tuple of (content, metadata)
        """
        content_parts = []
        metadata = {}
        
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                
                metadata["total_pages"] = len(pdf_reader.pages)
                
                # Extract PDF metadata
                if pdf_reader.metadata:
                    metadata["pdf_title"] = pdf_reader.metadata.get("/Title", "")
                    metadata["pdf_author"] = pdf_reader.metadata.get("/Author", "")
                    metadata["pdf_subject"] = pdf_reader.metadata.get("/Subject", "")
                
                # Extract text from each page
                for page_num, page in enumerate(pdf_reader.pages, 1):
                    try:
                        text = page.extract_text()
                        if text:
                            content_parts.append(text)
                        
                        # Add page break indicator
                        content_parts.append(f"\n--- Page {page_num} ---\n")
                    except Exception as e:
                        # Skip problematic pages but continue processing
                        print(f"  Warning: PyPDF2 could not extract page {page_num}: {str(e)[:60]}")
                        content_parts.append(f"\n--- Page {page_num} (extraction error) ---\n")
                        continue
        
        except Exception as e:
            raise RuntimeError(f"PyPDF2 failed to process PDF: {e}")
        
        content = "\n".join(content_parts)
        return content, metadata

    def _table_to_text(self, table: List[List]) -> str:
        """
        Convert a table to readable text format.
        
        Args:
            table: Table extracted as list of lists
            
        Returns:
            Formatted text representation of table
        """
        if not table:
            return ""
        
        lines = []
        for row in table:
            # Convert None values to empty strings
            row_values = [str(cell) if cell is not None else "" for cell in row]
            lines.append(" | ".join(row_values))
        
        return "\n".join(lines)

    def _extract_text_metadata(self, content: str, filename: str) -> Dict[str, Any]:
        """
        Extract metadata from the text content (e.g., report name, publication date).
        Specifically designed for KNBS documents.
        
        Args:
            content: Document content
            filename: Original filename
            
        Returns:
            Dictionary of extracted metadata
        """
        metadata = {"source": filename}
        
        # Extract publication date patterns
        date_patterns = [
            r"Published?:?\s*([A-Za-z]+\s+\d{4})",
            r"Publication Date:?\s*([A-Za-z]+\s+\d{1,2},?\s+\d{4})",
            r"Report Date:?\s*([A-Za-z]+\s+\d{4})",
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                metadata["publication_date"] = match.group(1)
                break
        
        # Extract data period
        period_pattern = r"Data Period:?\s*([^\.]+\d{4}[^\.])"
        match = re.search(period_pattern, content, re.IGNORECASE)
        if match:
            metadata["data_period"] = match.group(1).strip()
        
        # Extract report type
        if "census" in content.lower():
            metadata["report_type"] = "Census"
        elif "survey" in content.lower():
            metadata["report_type"] = "Survey"
        elif "report" in content.lower():
            metadata["report_type"] = "Report"
        else:
            metadata["report_type"] = "Document"
        
        # Extract organization (KNBS is standard)
        if "knbs" in content.lower() or "national bureau of statistics" in content.lower():
            metadata["organization"] = "KNBS"
        
        return metadata

    def _count_pages(self, file_path: str) -> int:
        """
        Count pages in PDF file.
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            Number of pages
        """
        try:
            if PYPDF2_AVAILABLE:
                with open(file_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    return len(pdf_reader.pages)
        except Exception:
            pass
        
        return 1  # Default if unable to determine

    def process_directory(self, directory_path: str) -> List[Dict[str, Any]]:
        """
        Process all PDF and text files in a directory.
        
        Args:
            directory_path: Path to directory containing documents
            
        Returns:
            List of processed documents with content and metadata
        """
        documents = []
        directory_path = Path(directory_path)
        
        if not directory_path.exists():
            raise FileNotFoundError(f"Directory not found: {directory_path}")
        
        # Find all PDF and text files
        for file_ext in ["*.pdf", "*.txt"]:
            for file_path in directory_path.glob(file_ext):
                try:
                    print(f"Processing: {file_path.name}")
                    doc = self.process_pdf_file(str(file_path))
                    documents.append(doc)
                except Exception as e:
                    print(f"Error processing {file_path.name}: {e}")
                    continue
        
        print(f"Successfully processed {len(documents)} documents")
        return documents

    @staticmethod
    def extract_statistics_from_content(content: str) -> Dict[str, List[str]]:
        """
        Extract statistical values and measurements from document content.
        Useful for identifying key data points in KNBS documents.
        
        Args:
            content: Document content
            
        Returns:
            Dictionary with extracted statistics
        """
        statistics = {"percentages": [], "absolute_numbers": []}
        
        # Find percentages (e.g., 34.2%, 5.1 percent)
        percentage_pattern = r"(\d+\.?\d*)\s*%"
        statistics["percentages"] = re.findall(percentage_pattern, content)
        
        # Find large numbers (likely statistics)
        number_pattern = r"(\d{1,3}(?:,\d{3})+|\d{4,})\s*(?:million|billion|thousand|persons?|hectares?|tonnes?|kg|tons?|liters?|metric)"
        statistics["absolute_numbers"] = re.findall(number_pattern, content, re.IGNORECASE)
        
        return statistics


# Example usage and testing
if __name__ == "__main__":
    processor = PDFProcessor()
    
    # Test with a sample directory
    sample_data_dir = "data"
    if os.path.exists(sample_data_dir):
        documents = processor.process_directory(sample_data_dir)
        print(f"\nProcessed {len(documents)} documents")
        for doc in documents:
            print(f"- {doc['metadata'].get('source', 'Unknown')}: "
                  f"{len(doc['content'])} characters")
