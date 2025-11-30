## Switching to `python app.py` and Installing PDF Support

### What Changed

**1. app.py is now the main entry point** ✓
- Updated `main()` function with better initialization messages
- Displays KNBS system header and instructions
- Shows example questions
- Better error handling and troubleshooting info
- Supports both text-based and PDF documents

**Previous command:** `python test_phase2.py`
**New command:** `python src/app.py`

---

## Installing PDF Libraries

You need to install two PDF processing libraries to eliminate the warnings:

### **Quick Install (Recommended)**

Open PowerShell in your venv and run:

```powershell
# Make sure you're in the venv
cd c:\Users\tim\Desktop\RAG_Application\RAG-Skeleton

# Activate venv (if not already activated)
.\venv\Scripts\Activate.ps1

# Install the PDF libraries
pip install pdfplumber PyPDF2
```

Or install both at once:
```powershell
pip install pdfplumber==0.10.3 PyPDF2==4.0.1
```

### **Alternative: Install from Updated requirements.txt**

```powershell
cd c:\Users\tim\Desktop\RAG_Application\RAG-Skeleton
pip install -r requirements.txt
```

This will install everything, including the newly added PDF libraries:
- `pdfplumber==0.10.3` - Added ✓
- `PyPDF2==4.0.1` - Added ✓

---

## What Each Library Does

**pdfplumber** (Primary - Preferred):
- Better at preserving PDF structure
- Excellent for extracting tables
- Ideal for statistical documents with complex layouts
- More accurate text extraction

**PyPDF2** (Fallback - Automatic):
- Lightweight PDF text extraction
- Used if pdfplumber isn't available
- Works as a backup method
- Good for simple PDFs

---

## Verification

After installation, verify the libraries are working:

```powershell
python -c "import pdfplumber; print('✓ pdfplumber installed')"
python -c "import PyPDF2; print('✓ PyPDF2 installed')"
```

Both should output success messages.

---

## Running the Updated System

### **Option 1: Interactive Mode (Recommended for testing)**
```powershell
cd c:\Users\tim\Desktop\RAG_Application\RAG-Skeleton
python src/app.py
```

This will:
1. Initialize the KNBS RAG Assistant
2. Load all documents from `src/data/`
3. Start an interactive session where you can ask questions
4. Type `quit` to exit

### **Option 2: One-time Query**
You can also create a simple test script that queries once and exits.

---

## Expected Output After Updates

```
======================================================================
  KENYA NATIONAL BUREAU OF STATISTICS - RAG ASSISTANT
======================================================================

[1/3] Initializing RAG Assistant...
Loading embedding model: sentence-transformers/all-MiniLM-L6-v2
Vector database initialized with collection: knbs_statistical_reports
✓ RAG Assistant initialized successfully!

[2/3] Loading documents from data directory...
Loaded document: kenya_economic_survey_2024.txt
Loaded document: census_2019_demographic_report.txt
Loaded document: agricultural_sector_report_2024.txt
Loaded document: inflation_and_prices_2020_2024.txt
✓ Loaded 4 document(s):
   - kenya_economic_survey_2024.txt: 15,234 characters
   - census_2019_demographic_report.txt: 18,567 characters
   - agricultural_sector_report_2024.txt: 22,891 characters
   - inflation_and_prices_2020_2024.txt: 25,123 characters

[3/3] Ingesting documents into vector database...
Total chunks created: 156
Processing batch 1/1 (Chunks 0 to 156)...
✓ Documents ingested successfully!

======================================================================
  SYSTEM READY - Enter your questions about KNBS data
======================================================================

Example questions:
  • What was Kenya's inflation rate in May 2024?
  • What is the population of Nairobi County?
  • What was the total maize production in 2023?

Type 'quit' or 'exit' to end the session
======================================================================

You: 
```

**Notice: No PDF warnings should appear after installing pdfplumber and PyPDF2**

---

## Troubleshooting

### **Still Seeing "pdfplumber not installed" warning?**

1. Verify installation:
   ```powershell
   pip list | grep -E "(pdfplumber|PyPDF2)"
   ```
   
   Should show both packages listed.

2. If not installed, run:
   ```powershell
   pip install pdfplumber PyPDF2 --upgrade
   ```

3. Restart Python/your terminal after installation

### **Permission Errors During Installation?**

If you get "Permission denied" errors:

```powershell
# Upgrade pip first
python -m pip install --upgrade pip

# Then install packages
pip install pdfplumber PyPDF2
```

### **Virtual Environment Issues?**

Make sure you're in the venv:
```powershell
# Check if venv is active (should show "(venv)" in prompt)
# If not, activate it:
.\venv\Scripts\Activate.ps1

# Then install
pip install pdfplumber PyPDF2
```

---

## Summary of Changes

| Item | Before | After |
|------|--------|-------|
| Main command | `python test_phase2.py` | `python src/app.py` ✓ |
| PDF libraries | Not installed (warnings) | Added to requirements.txt ✓ |
| Startup messages | Basic | Enhanced with KNBS header ✓ |
| Example questions | None | Displayed in startup ✓ |
| Error handling | Generic | Detailed troubleshooting ✓ |

---

## Next: Phase 3 - Production Data

Once you've confirmed the system works with `python src/app.py`, you're ready for Phase 3:

1. Download real KNBS PDF reports from knbs.or.ke
2. Place them in `src/data/` folder
3. Run `python src/app.py` again
4. The system will automatically process and ingest the PDFs
5. Query using real KNBS data

---

**Ready to go live! 🎉**
