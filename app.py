#!/usr/bin/env python
"""
Wrapper script to run the KNBS RAG Assistant from the root directory.
This allows running 'python app.py' instead of 'python src/app.py'
"""

import sys
import os

# Add src directory to Python path
src_path = os.path.join(os.path.dirname(__file__), 'src')
sys.path.insert(0, src_path)

# Import and run the main app
from app import main

if __name__ == "__main__":
    main()
