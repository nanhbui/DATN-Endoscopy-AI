
import os
import sys
from typing import List, Optional, Dict, Any
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, HTTPException, BackgroundTasks, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Add backend directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from rag.data_processor import DataProcessor
from rag.chatbot_rag import ProductRAGChatbot
from database.pydantic_models import ProductRecord

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="Product RAG Chatbot API",
    description="Multi-view product capture system with RAG-powered chatbot",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global instances (initialized on startup)
data_processor: Optional[DataProcessor] = None
chatbot: Optional[ProductRAGChatbot] = None


# ============================================================================
# Pydantic Models (Request/Response)
# ============================================================================

class HealthResponse(BaseModel):
    """Health check response"""
    status: str = Field(..., description="Service status")
    timestamp: str = Field(..., description="Current timestamp")
    mongodb_connected: bool = Field(..., description="MongoDB connection status")
    vector_store_available: bool = Field(..., description="Vector store availability")
    langsmith_enabled: bool = Field(..., description="LangSmith tracing status")


class ProcessSessionRequest(BaseModel):
    """Request to process a capture session"""
    metadata_file_path: str = Field(..., description="Path to metadata.json file")
    product_id: Optional[str] = Field(None, description="Optional product identifier")
    notes: Optional[str] = Field(None, description="Optional notes")


class ProcessSessionResponse(BaseModel):
    """Response after processing a session"""
    success: bool = Field(..., description="Processing success status")
    session_id: str = Field(..., description="Session identifier")
    message: str = Field(..., description="Status message")
    product_record: Optional[Dict[str, Any]] = Field(None, description="Processed product record")


class BatchProcessRequest(BaseModel):
    """Request to batch process sessions"""
    process_all: bool = Field(True, description="Process all unprocessed sessions")
    session_ids: Optional[List[str]] = Field(None, description="Specific session IDs to process")


class BatchProcessResponse(BaseModel):
    """Response after batch processing"""
    success: bool = Field(..., description="Batch processing success status")
    total_sessions: int = Field(..., description="Total sessions found")
    processed_count: int = Field(..., description="Number of sessions processed")
    skipped_count: int = Field(..., description="Number of sessions skipped")
    failed_count: int = Field(..., description="Number of sessions failed")
    session_ids_processed: List[str] = Field(..., description="List of processed session IDs")
    message: str = Field(..., description="Status message")


class ChatQueryRequest(BaseModel):
    """Request to query the chatbot"""
    query: str = Field(..., description="Natural language query", min_length=1)
    session_id: Optional[str] = Field(None, description="Optional session context")


class ChatQueryResponse(BaseModel):
    """Response from chatbot query"""
    query: str = Field(..., description="Original query")
    response: str = Field(..., description="Chatbot response")
    classification: str = Field(..., description="Query classification (in_scope/out_of_scope)")
    confidence: float = Field(..., description="Classification confidence")
    sources_count: int = Field(..., description="Number of RAG sources used")
    metadata: Dict[str, Any] = Field(..., description="Additional metadata")


class VectorStoreStatus(BaseModel):
    """Vector store status information"""
    available: bool = Field(..., description="Vector store availability")
    document_count: int = Field(..., description="Number of documents indexed")
    collection_name: str = Field(..., description="ChromaDB collection name")


class SystemStatusResponse(BaseModel):
    """System status information"""
    mongodb_status: str = Field(..., description="MongoDB status")
    total_products: int = Field(..., description="Total products in database")
    vector_store: VectorStoreStatus = Field(..., description="Vector store information")
    langsmith_enabled: bool = Field(..., description="LangSmith tracing status")
    langsmith_project: Optional[str] = Field(None, description="LangSmith project name")


class ProductListResponse(BaseModel):
    """List of products"""
    total_count: int = Field(..., description="Total number of products")
    products: List[Dict[str, Any]] = Field(..., description="List of product records")


# ============================================================================
# Startup/Shutdown Events
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    global data_processor, chatbot

    print("\n" + "="*60)
    print("STARTING PRODUCT RAG CHATBOT API SERVER")
    print("="*60)

    try:
        # Initialize DataProcessor
        print("[INFO] Initializing DataProcessor...")
        data_processor = DataProcessor()
        print("[SUCCESS] DataProcessor initialized")

        # Initialize vector store if needed
        print("[INFO] Checking vector store...")
        vector_store = data_processor.get_vector_store()
        if vector_store:
            print("[SUCCESS] Vector store ready")

        # Initialize Chatbot
        print("[INFO] Initializing ProductRAGChatbot...")
        chatbot = ProductRAGChatbot(
            data_processor=data_processor,
            product_context="Product X - Multi-angle captured products"
        )
        print("[SUCCESS] ProductRAGChatbot initialized")

        print("\n[INFO] API Server ready!")
        print("[INFO] Visit http://localhost:8000/docs for API documentation")
        print("="*60 + "\n")

    except Exception as e:
        print(f"[ERROR] Failed to initialize services: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    global data_processor

    print("\n[INFO] Shutting down API server...")
    if data_processor:
        data_processor.close()
    print("[INFO] Cleanup complete. Goodbye!")


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/", response_model=Dict[str, str])
async def root():
    """Root endpoint - API information"""
    return {
        "name": "Product RAG Chatbot API",
        "version": "1.0.0",
        "description": "Multi-view product capture system with RAG-powered chatbot",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    try:
        # Check MongoDB connection
        mongodb_connected = False
        if data_processor and data_processor.mongo_collection:
            try:
                data_processor.mongo_client.server_info()
                mongodb_connected = True
            except:
                pass

        # Check vector store
        vector_store_available = False
        if data_processor:
            vs = data_processor.get_vector_store()
            if vs:
                try:
                    count = vs._collection.count()
                    vector_store_available = count > 0
                except:
                    pass

        # Check LangSmith
        langsmith_enabled = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"

        return HealthResponse(
            status="healthy" if mongodb_connected else "degraded",
            timestamp=datetime.now().isoformat(),
            mongodb_connected=mongodb_connected,
            vector_store_available=vector_store_available,
            langsmith_enabled=langsmith_enabled
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Health check failed: {str(e)}"
        )


@app.get("/status", response_model=SystemStatusResponse)
async def system_status():
    """Get detailed system status"""
    try:
        if not data_processor:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="DataProcessor not initialized"
            )

        # Get product count
        products = data_processor.get_all_product_records()
        total_products = len(products)

        # Get vector store status
        vs = data_processor.get_vector_store()
        vector_store_info = VectorStoreStatus(
            available=vs is not None,
            document_count=vs._collection.count() if vs else 0,
            collection_name="product_knowledge"
        )

        # LangSmith status
        langsmith_enabled = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
        langsmith_project = os.getenv("LANGCHAIN_PROJECT") if langsmith_enabled else None

        return SystemStatusResponse(
            mongodb_status="connected",
            total_products=total_products,
            vector_store=vector_store_info,
            langsmith_enabled=langsmith_enabled,
            langsmith_project=langsmith_project
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get system status: {str(e)}"
        )


@app.post("/process/session", response_model=ProcessSessionResponse)
async def process_session(request: ProcessSessionRequest, background_tasks: BackgroundTasks):
    """Process a single capture session"""
    try:
        if not data_processor:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="DataProcessor not initialized"
            )

        # Validate file exists
        if not Path(request.metadata_file_path).exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Metadata file not found: {request.metadata_file_path}"
            )

        # Process session
        print(f"[INFO] Processing session: {request.metadata_file_path}")
        product_record = data_processor.process_session_metadata(
            metadata_file_path=request.metadata_file_path,
            product_id=request.product_id,
            notes=request.notes
        )

        if not product_record:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to process session"
            )

        # Reinitialize vector store in background
        background_tasks.add_task(data_processor.initialize_vector_store)

        return ProcessSessionResponse(
            success=True,
            session_id=product_record.session_id,
            message=f"Session {product_record.session_id} processed successfully",
            product_record=product_record.model_dump()
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Processing failed: {str(e)}"
        )


@app.post("/process/batch", response_model=BatchProcessResponse)
async def batch_process(request: BatchProcessRequest, background_tasks: BackgroundTasks):
    """Batch process multiple sessions"""
    try:
        if not data_processor:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="DataProcessor not initialized"
            )

        # Find all metadata files
        captured_images = Path("captured_images")
        if not captured_images.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="captured_images directory not found"
            )

        all_metadata_files = list(captured_images.glob("*/metadata.json"))

        if not all_metadata_files:
            return BatchProcessResponse(
                success=True,
                total_sessions=0,
                processed_count=0,
                skipped_count=0,
                failed_count=0,
                session_ids_processed=[],
                message="No metadata files found"
            )

        # Determine which sessions to process
        unprocessed_files = []
        skipped_count = 0

        for metadata_file in all_metadata_files:
            import json
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
                session_id = metadata.get('session_id')

            # Check if already processed
            existing_record = data_processor.get_product_record(session_id)
            if existing_record:
                skipped_count += 1
                continue

            # Filter by session_ids if specified
            if request.session_ids and session_id not in request.session_ids:
                continue

            unprocessed_files.append((session_id, str(metadata_file)))

        # Process unprocessed sessions
        processed_ids = []
        failed_count = 0

        for session_id, metadata_file in unprocessed_files:
            try:
                print(f"[INFO] Processing session {session_id}...")
                product_record = data_processor.process_session_metadata(metadata_file)
                if product_record:
                    processed_ids.append(session_id)
                else:
                    failed_count += 1
            except Exception as e:
                print(f"[ERROR] Failed to process {session_id}: {e}")
                failed_count += 1

        # Reinitialize vector store if any sessions were processed
        if processed_ids:
            background_tasks.add_task(data_processor.initialize_vector_store)

        return BatchProcessResponse(
            success=True,
            total_sessions=len(all_metadata_files),
            processed_count=len(processed_ids),
            skipped_count=skipped_count,
            failed_count=failed_count,
            session_ids_processed=processed_ids,
            message=f"Processed {len(processed_ids)} sessions, skipped {skipped_count}, failed {failed_count}"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch processing failed: {str(e)}"
        )


@app.post("/chat/query", response_model=ChatQueryResponse)
async def chat_query(request: ChatQueryRequest):
    """Query the chatbot with natural language"""
    try:
        if not chatbot:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Chatbot not initialized"
            )

        # Execute query through chatbot workflow
        print(f"[INFO] Processing query: {request.query}")

        # Create initial state
        from pydantic_models import AgentState
        initial_state = AgentState(user_query=request.query)

        # Run workflow
        final_state = chatbot.workflow.invoke(initial_state)

        # Extract response
        response_text = final_state.get("final_response", "No response generated")
        classification_result = final_state.get("classification")
        rag_results = final_state.get("rag_results", [])

        # Build metadata
        metadata = {
            "classification_confidence": classification_result.confidence if classification_result else 0.0,
            "classification_reason": classification_result.reason if classification_result else "",
            "rag_sources": len(rag_results),
            "tool_calls": len(final_state.get("tool_calls", []))
        }

        return ChatQueryResponse(
            query=request.query,
            response=response_text,
            classification=classification_result.classification.value if classification_result else "unknown",
            confidence=classification_result.confidence if classification_result else 0.0,
            sources_count=len(rag_results),
            metadata=metadata
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query processing failed: {str(e)}"
        )


@app.get("/products", response_model=ProductListResponse)
async def list_products(
    limit: int = 100,
    offset: int = 0,
    session_id: Optional[str] = None
):
    """Get list of products"""
    try:
        if not data_processor:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="DataProcessor not initialized"
            )

        # Get all products
        if session_id:
            product = data_processor.get_product_record(session_id)
            products = [product] if product else []
        else:
            products = data_processor.get_all_product_records()

        # Apply pagination
        total_count = len(products)
        products_page = products[offset:offset + limit]

        # Convert to dict
        products_dict = [p.model_dump() for p in products_page]

        return ProductListResponse(
            total_count=total_count,
            products=products_dict
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list products: {str(e)}"
        )


@app.get("/products/{session_id}", response_model=Dict[str, Any])
async def get_product(session_id: str):
    """Get a specific product by session ID"""
    try:
        if not data_processor:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="DataProcessor not initialized"
            )

        product = data_processor.get_product_record(session_id)
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product not found: {session_id}"
            )

        return product.model_dump()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get product: {str(e)}"
        )


@app.post("/vector-store/reinitialize")
async def reinitialize_vector_store(background_tasks: BackgroundTasks):
    """Reinitialize vector store from MongoDB"""
    try:
        if not data_processor:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="DataProcessor not initialized"
            )

        # Run in background
        background_tasks.add_task(data_processor.initialize_vector_store)

        return {
            "success": True,
            "message": "Vector store reinitialization started in background"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reinitialize vector store: {str(e)}"
        )


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    # Run server
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
