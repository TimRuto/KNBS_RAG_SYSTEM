import os
import chromadb
from typing import List, Dict, Any
from sentence_transformers import SentenceTransformer
from langchain_text_splitters import RecursiveCharacterTextSplitter 
import uuid 
import math

# Optional PDF processor import
try:
    from pdf_processor import PDFProcessor
    PDF_SUPPORT_AVAILABLE = True
except ImportError:
    PDF_SUPPORT_AVAILABLE = False
    print("Note: PDF processor not available. Text files can still be processed.")

class VectorDB:
    """
    A vector database wrapper using ChromaDB and SentenceTransformer embeddings.
    Handles document chunking, embedding, storage, and semantic search.
    """

    def __init__(self, collection_name: str, embedding_model: str, persist_directory: str):
        """
        Initialize the vector database.
        
        Args:
            collection_name: Name of the ChromaDB collection.
            embedding_model: HuggingFace model name for embeddings.
            persist_directory: Local directory path to store ChromaDB files.
        """
        self.collection_name = collection_name
        self.embedding_model_name = embedding_model

        # Initialize ChromaDB client using the config path
        self.client = chromadb.PersistentClient(path=persist_directory) 

        # Load embedding model manually for query time and ingestion
        print(f"Loading embedding model: {self.embedding_model_name}")
        self.embedding_model = SentenceTransformer(self.embedding_model_name)

        # Get or create collection (without passing embedding_function, as we calculate embeddings manually)
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"description": "RAG document collection"},
        )

        print(f"Vector database initialized with collection: {self.collection_name}")
        print(f"Current documents in collection: {self.collection.count()}")


    def chunk_text(self, text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
        """
        Implement text chunking logic using RecursiveCharacterTextSplitter.
        """
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            # Common separators for good semantic chunking
            separators=["\n\n", "\n", " ", ""]
        )
        chunks = text_splitter.split_text(text)
        return chunks

    def add_documents(self, documents: List[Dict[str, Any]], chunk_size: int, chunk_overlap: int) -> None:
        """
        Add documents to the vector database. This handles chunking, embedding, and batching.
        Supports both pre-processed documents and raw file paths.

        Args:
            documents: List of dictionaries, each containing 'content' (str) and 'metadata' (dict).
                      OR list of file paths (strings ending in .pdf or .txt)
            chunk_size: The size of text chunks.
            chunk_overlap: The overlap between chunks.
        """
        # If documents are file paths, process them first
        if documents and isinstance(documents[0], str):
            documents = self._process_file_paths(documents)
        
        all_chunks_text = []
        all_metadatas = []
        all_ids = []
        
        # Determine the next ID to avoid collisions when adding new data
        start_id = self.collection.count()
        current_chunk_index = 0
        
        for doc in documents:
            content = doc["content"]
            metadata = doc.get("metadata", {})
            source = metadata.get("source", f"unknown_doc_{uuid.uuid4().hex[:6]}.txt")
            
            # 1. Chunk the document
            chunks = self.chunk_text(content, chunk_size, chunk_overlap)
            
            # 2. Prepare data for insertion
            for i, chunk_content in enumerate(chunks):
                # Create a stable, unique ID for the chunk
                chunk_id = f"{source}_{current_chunk_index}"
                
                all_chunks_text.append(chunk_content)
                
                chunk_metadata = {
                    "source": source,
                    "length": len(chunk_content),
                    **metadata # Include any existing metadata
                }
                all_metadatas.append(chunk_metadata)
                
                all_ids.append(chunk_id)
                current_chunk_index += 1
            
        print(f"Total chunks created: {len(all_chunks_text)}")
        
        if not all_chunks_text:
            print("No content to embed and store.")
            return

        # 3. Batching for Scalability (e.g., process 500 chunks at a time)
        BATCH_SIZE = 500 
        num_batches = math.ceil(len(all_chunks_text) / BATCH_SIZE)
        
        for i in range(num_batches):
            start_idx = i * BATCH_SIZE
            end_idx = min((i + 1) * BATCH_SIZE, len(all_chunks_text))
            
            batch_texts = all_chunks_text[start_idx:end_idx]
            batch_metadatas = all_metadatas[start_idx:end_idx]
            batch_ids = all_ids[start_idx:end_idx]
            
            print(f"Processing batch {i+1}/{num_batches} (Chunks {start_idx} to {end_idx})...")

            # Create embeddings for the batch
            embeddings = self.embedding_model.encode(batch_texts).tolist()
            
            # Store in ChromaDB collection
            self.collection.add(
                embeddings=embeddings,
                documents=batch_texts,
                metadatas=batch_metadatas,
                ids=batch_ids,
            )
        
        print(f"Documents added successfully. New total: {self.collection.count()} chunks.")

    def _process_file_paths(self, file_paths: List[str]) -> List[Dict[str, Any]]:
        """
        Process file paths and extract document content.
        
        Args:
            file_paths: List of file paths (.pdf or .txt)
            
        Returns:
            List of documents with content and metadata
        """
        if not PDF_SUPPORT_AVAILABLE:
            print("Warning: PDF processing not available. Processing text files only...")
        
        documents = []
        processor = PDFProcessor() if PDF_SUPPORT_AVAILABLE else None
        
        for file_path in file_paths:
            try:
                if file_path.endswith('.pdf'):
                    if not PDF_SUPPORT_AVAILABLE:
                        print(f"Skipping PDF file (not supported): {file_path}")
                        continue
                    doc = processor.process_pdf_file(file_path)
                    documents.append(doc)
                    print(f"Processed: {os.path.basename(file_path)}")
                elif file_path.endswith('.txt'):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    documents.append({
                        "content": content,
                        "metadata": {"source": os.path.basename(file_path)}
                    })
                    print(f"Processed: {os.path.basename(file_path)}")
            except Exception as e:
                print(f"Error processing {file_path}: {e}")
                continue
        
        return documents

    def search(self, query: str, n_results: int = 5, distance_threshold: float = 0.4) -> Dict[str, Any]:
        """
        Search for similar documents in the vector database and filter by distance threshold.

        Args:
            query: Search query
            n_results: Number of results to return
            distance_threshold: Maximum distance allowed for a chunk to be considered relevant.

        Returns:
            Dictionary containing filtered search results: 'documents', 'metadatas', 'distances', 'ids'
        """
        
        # 1. Create query embedding
        try:
            query_embedding = self.embedding_model.encode([query]).tolist()
        except Exception as e:
            print(f"Error encoding query: {e}")
            return { "documents": [], "metadatas": [], "distances": [], "ids": [] }
        
        # 2. Query the vector database
        try:
            # We must include "metadatas" for the LLM to access the "source" for citation
            results = self.collection.query(
                query_embeddings=query_embedding,
                n_results=n_results,
                include=["documents", "metadatas", "distances"]
            )
            
            if not results or not results["documents"] or not results["documents"][0]:
                return { "documents": [], "metadatas": [], "distances": [], "ids": [] }

            # Flatten the results (Chroma returns lists of lists)
            documents = results["documents"][0]
            metadatas = results["metadatas"][0]
            distances = results["distances"][0]
            ids = results["ids"][0]

            # 3. Filtering by Distance Threshold (Crucial RAG technique)
            
            filtered_documents = []
            filtered_metadatas = []
            filtered_distances = []
            filtered_ids = []

            for doc, metadata, distance, chunk_id in zip(documents, metadatas, distances, ids):
                # The distance metric is typically cosine distance (lower is better/closer).
                # Only include chunks where the distance is less than the specified threshold.
                if distance <= distance_threshold:
                    filtered_documents.append(doc)
                    filtered_metadatas.append(metadata)
                    filtered_distances.append(distance)
                    filtered_ids.append(chunk_id)
                else:
                    print(f"Filtering out chunk {chunk_id} with distance {distance:.4f} > threshold {distance_threshold:.4f}")
            
            return {
                "documents": filtered_documents,
                "metadatas": filtered_metadatas,
                "distances": filtered_distances,
                "ids": filtered_ids
            }
            
        except Exception as e:
            print(f"Error during vector search: {e}")
            return { "documents": [], "metadatas": [], "distances": [], "ids": [] }