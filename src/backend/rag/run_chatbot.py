import argparse
import os
import sys
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Import Phase 2 components
from data_processor import DataProcessor
from chatbot_rag import ProductRAGChatbot

# Load environment variables
load_dotenv()


def check_environment() -> bool:
    """
    Check if all required environment variables are set.

    Returns:
        True if all requirements met, False otherwise
    """
    required_vars = ["OPENAI_API_KEY"]
    optional_vars = ["TAVILY_API_KEY", "LANGCHAIN_API_KEY"]

    print("\n" + "="*60)
    print("ENVIRONMENT CHECK")
    print("="*60)

    all_ok = True

    for var in required_vars:
        value = os.getenv(var)
        if value:
            # Mask the key for security
            masked = value[:8] + "..." + value[-4:] if len(value) > 12 else "***"
            print(f"✓ {var}: {masked}")
        else:
            print(f"✗ {var}: NOT SET (REQUIRED)")
            all_ok = False

    for var in optional_vars:
        value = os.getenv(var)
        if value:
            masked = value[:8] + "..." + value[-4:] if len(value) > 12 else "***"
            print(f"✓ {var}: {masked} (optional)")
        else:
            print(f"- {var}: not set (optional)")

    print("="*60 + "\n")

    if not all_ok:
        print("[ERROR] Missing required environment variables!")
        print("[INFO] Please create a .env file with your API keys.")
        print("[INFO] You can copy .env.example to .env and fill in your keys.\n")
        return False

    return True


def initialize_data_processor(mongodb_uri: str = None) -> DataProcessor:
    """
    Initialize the data processor with MongoDB.

    Args:
        mongodb_uri: MongoDB connection URI (from env if not provided)

    Returns:
        DataProcessor instance
    """
    print("\n" + "="*60)
    print("INITIALIZING DATA PROCESSOR")
    print("="*60)

    mongodb_uri = mongodb_uri or os.getenv("MONGODB_URI")
    if not mongodb_uri:
        print("[ERROR] MONGODB_URI not set in environment")
        print("[INFO] Please set MONGODB_URI in your .env file")
        print("[INFO] Example: MONGODB_URI=mongodb://localhost:27017/")
        raise ValueError("MONGODB_URI is required")

    data_processor = DataProcessor(mongodb_uri=mongodb_uri)

    print("="*60 + "\n")

    return data_processor


def process_metadata_file(
    data_processor: DataProcessor,
    metadata_file: str
) -> bool:
    """
    Process a capture session metadata file.

    Args:
        data_processor: DataProcessor instance
        metadata_file: Path to metadata JSON file

    Returns:
        True if successful, False otherwise
    """
    print("\n" + "="*60)
    print("PROCESSING METADATA FILE")
    print("="*60)
    print(f"File: {metadata_file}\n")

    metadata_path = Path(metadata_file)

    if not metadata_path.exists():
        print(f"[ERROR] Metadata file not found: {metadata_file}")
        return False

    # Process the metadata
    product_record = data_processor.process_session_metadata(
        metadata_file_path=str(metadata_path),
        product_id=None,  # Optional: can be provided via CLI arg
        notes=f"Processed from {metadata_path.name}"
    )

    if product_record:
        print("\n[SUCCESS] Metadata processed successfully!")
        print(f"  Session ID: {product_record.session_id}")
        print(f"  Total Angles: {product_record.total_angles}")
        if product_record.mvv_result:
            print(f"  MVV Confidence: {product_record.mvv_result.confidence_score:.2f}")
            print(f"  MVV Verified: {product_record.mvv_result.verified}")
        print("="*60 + "\n")
        return True
    else:
        print("\n[ERROR] Failed to process metadata")
        print("="*60 + "\n")
        return False


def find_latest_metadata_file(search_dir: str = "captured_images") -> Optional[str]:
    """
    Find the most recent metadata file in a directory.

    Args:
        search_dir: Directory to search

    Returns:
        Path to latest metadata file or None
    """
    search_path = Path(search_dir)

    if not search_path.exists():
        return None

    # Find all metadata JSON files in session subdirectories
    # Pattern: captured_images/*/metadata.json
    metadata_files = list(search_path.glob("*/metadata.json"))

    if not metadata_files:
        return None

    # Sort by modification time (most recent first)
    latest_file = max(metadata_files, key=lambda p: p.stat().st_mtime)

    return str(latest_file)


def start_chatbot(
    data_processor: DataProcessor,
    product_context: str = "Product X"
) -> None:
    """
    Start the interactive RAG chatbot.

    Args:
        data_processor: DataProcessor instance
        product_context: Product context description
    """
    print("\n" + "="*60)
    print("STARTING RAG CHATBOT")
    print("="*60 + "\n")

    # Create chatbot
    chatbot = ProductRAGChatbot(
        data_processor=data_processor,
        product_context=product_context
    )

    # Start interactive chat
    chatbot.chat()


def main():
    """
    Main entry point for the chatbot runner.
    """
    parser = argparse.ArgumentParser(
        description="Interactive Product RAG Chatbot - Phase 2",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start chatbot (auto-detect latest metadata)
  python run_chatbot.py

  # Process specific metadata file then start chatbot
  python run_chatbot.py --process-metadata captured_images/session_20231205_143022_metadata.json

  # Reinitialize vector store from MongoDB
  python run_chatbot.py --reinitialize-vector-store

  # Use custom MongoDB URI
  python run_chatbot.py --mongodb-uri mongodb://localhost:27017/
        """
    )

    parser.add_argument(
        "--process-metadata",
        type=str,
        metavar="FILE",
        help="Path to metadata JSON file from Phase 1 capture"
    )

    parser.add_argument(
        "--auto-detect",
        action="store_true",
        default=True,
        help="Auto-detect and process unprocessed metadata files (default: True)"
    )

    parser.add_argument(
        "--process-all",
        action="store_true",
        help="Process all unprocessed sessions without prompting"
    )

    parser.add_argument(
        "--reinitialize-vector-store",
        action="store_true",
        help="Reinitialize vector store from MongoDB"
    )

    parser.add_argument(
        "--mongodb-uri",
        type=str,
        help="MongoDB connection URI (default: from .env MONGODB_URI)"
    )

    parser.add_argument(
        "--product-context",
        type=str,
        default="Product X - Multi-angle captured products",
        help="Product context description for chatbot"
    )

    parser.add_argument(
        "--skip-env-check",
        action="store_true",
        help="Skip environment variable check"
    )

    args = parser.parse_args()

    # Print header
    print("\n" + "="*60)
    print("PRODUCT RAG CHATBOT - PHASE 2")
    print("Multi-View Product Data Capture System")
    print("="*60)

    try:
        # Step 1: Check environment
        if not args.skip_env_check:
            if not check_environment():
                sys.exit(1)

        # Step 2: Initialize data processor
        data_processor = initialize_data_processor(
            mongodb_uri=args.mongodb_uri
        )

        # Step 3: Process metadata if specified
        metadata_processed = False

        if args.process_metadata:
            # Process specified metadata file
            metadata_processed = process_metadata_file(
                data_processor,
                args.process_metadata
            )
        elif args.auto_detect:
            # Auto-detect ALL metadata files and process unprocessed ones
            print("[INFO] Auto-detecting metadata files...")

            from pathlib import Path
            captured_images = Path("captured_images")
            all_metadata_files = list(captured_images.glob("*/metadata.json"))

            if not all_metadata_files:
                print("[INFO] No metadata files found in captured_images/")
            else:
                print(f"[INFO] Found {len(all_metadata_files)} session(s) in captured_images/")

                # Check which sessions are already processed
                unprocessed_files = []
                processed_count = 0

                for metadata_file in all_metadata_files:
                    # Read session_id from metadata
                    import json
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                        session_id = metadata.get('session_id')

                    # Check if already processed in MongoDB
                    existing_record = data_processor.get_product_record(session_id)
                    if existing_record:
                        print(f"   ✓ {session_id} - Already processed")
                        processed_count += 1
                    else:
                        print(f"   ○ {session_id} - Not yet processed")
                        unprocessed_files.append((session_id, str(metadata_file)))

                print(f"\n[SUMMARY] Processed: {processed_count}, Unprocessed: {len(unprocessed_files)}")

                if unprocessed_files:
                    print(f"\n[INFO] Found {len(unprocessed_files)} unprocessed session(s)")

                    # Check if --process-all flag is set
                    should_process = args.process_all

                    if not should_process:
                        response = input(f"Process all {len(unprocessed_files)} unprocessed sessions? [Y/n]: ").strip().lower()
                        should_process = response in ['', 'y', 'yes']

                    if should_process:
                        # Process all unprocessed files
                        for i, (session_id, metadata_file) in enumerate(unprocessed_files, 1):
                            print(f"\n{'='*60}")
                            print(f"Processing session {i}/{len(unprocessed_files)}: {session_id}")
                            print(f"{'='*60}")

                            success = process_metadata_file(
                                data_processor,
                                metadata_file
                            )

                            if success:
                                metadata_processed = True
                    else:
                        print("[INFO] Skipping processing")
                else:
                    print("\n[INFO] All sessions already processed!")

        # Step 4: Initialize or reinitialize vector store
        should_init_vector_store = args.reinitialize_vector_store or metadata_processed

        # Also check if there are processed records but vector store is empty
        if not should_init_vector_store:
            records = data_processor.get_all_product_records()
            if records:
                # Check if vector store exists and has data
                vs = data_processor.get_vector_store()
                if vs:
                    try:
                        # Try a test query to see if vector store has data
                        test_results = vs.similarity_search("test", k=1)
                        if not test_results:
                            print("[INFO] Vector store is empty but MongoDB has records")
                            should_init_vector_store = True
                    except:
                        print("[INFO] Vector store error detected, will reinitialize")
                        should_init_vector_store = True

        if should_init_vector_store:
            print("\n[INFO] Initializing vector store...")
            success = data_processor.initialize_vector_store()

            if success:
                print("[SUCCESS] Vector store initialized")
            else:
                print("[WARNING] Vector store initialization had issues")
                print("[INFO] Continuing anyway...")

        # Step 5: Start chatbot
        start_chatbot(
            data_processor=data_processor,
            product_context=args.product_context
        )

    except KeyboardInterrupt:
        print("\n\n[INFO] Interrupted by user. Exiting...")
        sys.exit(0)

    except Exception as e:
        print(f"\n[FATAL ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        # Cleanup
        if 'data_processor' in locals():
            data_processor.close()


if __name__ == "__main__":
    main()
