import os
import yaml
from typing import List, Dict, Any
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from vectordb import VectorDB
from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI

# Define the config and data directory paths
CONFIG_DIR = "config"
DATA_DIR = "data" 

# Load environment variables
load_dotenv()

def load_config(config_file: str) -> Dict[str, Any]:
    """Loads a YAML configuration file."""
    filepath = os.path.join(CONFIG_DIR, config_file)
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Error: Configuration file not found at {filepath}. Please ensure it exists.")
        return {}
    except Exception as e:
        print(f"Error loading configuration from {filepath}: {e}")
        return {}


def load_documents() -> List[Dict[str, Any]]:
    """
    Load ALL documents from the data directory.
    If the data directory contains no .txt files, a sample document is created for immediate functionality.
    """
    results = []
    
    # 1. Create data directory if it doesn't exist
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        print(f"Created data directory: {DATA_DIR}")
        
    # 2. Identify all .txt files
    file_list = [f for f in os.listdir(DATA_DIR) if f.endswith(".txt")]
    
    # 3. Fallback: Add a sample document if the directory has no .txt files
    if not file_list:
        sample_filename = "project_notes.txt"
        sample_path = os.path.join(DATA_DIR, sample_filename)
        with open(sample_path, "w", encoding="utf-8") as f:
            f.write(
                "Project Alpha Summary: The core objective is to minimize latency in the "
                "data ingestion pipeline, aiming for sub-100ms response times. "
                "We found that deploying the RAG component on a dedicated Groq LPU reduced "
                "end-to-end response time by 75% compared to standard cloud GPU instances. "
                "The current recommended chunk size for text documents is 800 characters, "
                "with an overlap of 150 characters, as determined by testing. "
                "The preferred embedding model is all-MiniLM-L6-v2."
            )
        file_list.append(sample_filename)
        print(f"Added sample document: {sample_filename} (Directory was empty)")

    # 4. Read documents
    for filename in file_list:
        filepath = os.path.join(DATA_DIR, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
                results.append({
                    "content": content,
                    "metadata": {"source": filename} # Source is critical for citation
                })
            print(f"Loaded document: {filename}")
        except Exception as e:
            print(f"Error loading {filename}: {e}")
            
    return results


class RAGAssistant:
    """
    A simple RAG-based AI assistant using ChromaDB and multiple LLM providers.
    Supports OpenAI, Groq, and Google Gemini APIs.
    """

    def __init__(self):
        """Initialize the RAG assistant, loading configurations and setting up components."""
        
        # Load configs
        self.config = load_config("config.yaml")
        self.prompt_config = load_config("prompt_config.yaml")
        
        # --- Config Values (Read from config.yaml) ---
        self.k_chunks = self.config.get("retrieval", {}).get("top_k", 5)
        self.distance_threshold = self.config.get("retrieval", {}).get("distance_threshold", 0.4)
        self.chunk_size = self.config.get("chunking", {}).get("chunk_size", 800)
        self.chunk_overlap = self.config.get("chunking", {}).get("chunk_overlap", 150)
        
        llm_config = self.config.get("llm", {})
        self.llm_temperature = llm_config.get("temperature", 0.0)

        # --- Initialize LLM ---
        self.llm = self._initialize_llm(llm_config)
        if not self.llm:
            raise ValueError("LLM initialization failed. Check your API keys and models.") 

        # --- Initialize Vector Database ---
        db_config = self.config.get("vectordb", {})
        
        self.vector_db = VectorDB(
            collection_name=db_config.get("collection_name", "rag_documents"),
            embedding_model=db_config.get("embedding_model", "sentence-transformers/all-MiniLM-L6-v2"),
            persist_directory=db_config.get("persist_directory", "./vector_db")
        )

        # --- Create RAG prompt template ---
        template_string = self.prompt_config.get("rag_assistant_prompt", {}).get("template")
        
        if not template_string:
             raise ValueError("Prompt template not found in prompt_config.yaml. Check the file structure.")

        self.prompt_template = ChatPromptTemplate.from_template(template_string)
        
        # Create the chain: Prompt -> LLM -> OutputParser
        self.chain = self.prompt_template | self.llm | StrOutputParser()

        print("RAG Assistant initialized successfully")

    def _initialize_llm(self, llm_config: Dict[str, Any]):
        """
        Initialize the LLM by checking for available API keys based on configured priority.
        """
        openai_model = llm_config.get("openai_model", "gpt-4o-mini")
        groq_model = llm_config.get("groq_model", "llama-3.1-8b-instant")
        google_model = llm_config.get("google_model", "gemini-2.0-flash")

        # Priority: Groq > OpenAI > Google (based on typical RAG performance/cost preference)
        if os.getenv("GROQ_API_KEY"):
            print(f"Using Groq model: {groq_model}")
            return ChatGroq(
                api_key=os.getenv("GROQ_API_KEY"), model=groq_model, temperature=self.llm_temperature
            )

        elif os.getenv("OPENAI_API_KEY"):
            print(f"Using OpenAI model: {openai_model}")
            return ChatOpenAI(
                api_key=os.getenv("OPENAI_API_KEY"), model=openai_model, temperature=self.llm_temperature
            )

        elif os.getenv("GOOGLE_API_KEY"):
            print(f"Using Google Gemini model: {google_model}")
            return ChatGoogleGenerativeAI(
                google_api_key=os.getenv("GOOGLE_API_KEY"),
                model=google_model,
                temperature=self.llm_temperature,
            )

        else:
            print("Error: No valid API key found.")
            return None

    def add_documents(self, documents: List[Dict[str, Any]]) -> None:
        """
        Add documents to the knowledge base using the configured chunking parameters.
        """
        self.vector_db.add_documents(documents, self.chunk_size, self.chunk_overlap)

    def invoke(self, input: str) -> str:
        """
        Query the RAG assistant: Retrieval, Context Building, and Generation.

        Args:
            input: User's question.

        Returns:
            The LLM's generated answer string.
        """
        # 1. Retrieval: Get context chunks from the vector database
        search_results = self.vector_db.search(
            query=input, 
            n_results=self.k_chunks, 
            distance_threshold=self.distance_threshold
        )
        
        retrieved_chunks = search_results.get("documents", [])
        retrieved_metadatas = search_results.get("metadatas", [])
        
        # 2. Refusal Check: If retrieval fails to find relevant chunks
        if not retrieved_chunks:
            # Using the exact refusal phrase defined in prompt_config.yaml
            return "I apologize, I cannot find that specific information in the provided knowledge base."

        # 3. Context Building: Concatenate the retrieved chunks with source information
        context_parts = []
        for chunk, metadata in zip(retrieved_chunks, retrieved_metadatas):
            # Format context with source information, CRITICAL for mandatory citation
            source = metadata.get("source", "unknown_source.txt")
            context_parts.append(f"--- Document Source: {source} ---\n{chunk}")
            
        context_string = "\n\n".join(context_parts)
        
        # 4. Prompt Building and LLM Invocation
        try:
            llm_answer = self.chain.invoke({
                "context": context_string,
                "question": input
            })
            
            return llm_answer
        
        except Exception as e:
            return f"An error occurred during LLM generation: {e}"


def main():
    """Main function to demonstrate the RAG assistant."""
    try:
        # Create config directory if it doesn't exist (needed for YAML loading)
        if not os.path.exists(CONFIG_DIR):
             os.makedirs(CONFIG_DIR)
             print(f"Created config directory: {CONFIG_DIR}")
        
        # Initialize the RAG assistant
        print("Initializing RAG Assistant...")
        assistant = RAGAssistant()

        # Load sample documents (will load all .txt files)
        print("\nLoading documents...")
        sample_docs = load_documents()

        # Ingest documents into the vector database
        assistant.add_documents(sample_docs)

        print("\n--- RAG System Ready ---")
        done = False

        while not done:
            question = input("\nEnter a question or 'quit' to exit: ")
            if question.lower() == "quit":
                done = True
            else:
                result = assistant.invoke(question) # Corrected function name from .query()
                print("-" * 50)
                print(f"ASSISTANT: {result}")
                print("-" * 50)

    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        print("=" * 50)
        print("TROUBLESHOOTING:")
        print("1. Ensure your '.env' file is correctly set up with at least one API key.")
        print("2. Ensure the 'config/' directory exists and contains 'config.yaml' and 'prompt_config.yaml'.")
        print("3. Check the console output for any errors during LLM or DB initialization.")
        print("=" * 50)


if __name__ == "__main__":
    main()