import os
import json
import base64
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from dotenv import load_dotenv

# MongoDB
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, DuplicateKeyError

# OpenAI for Vision
from openai import OpenAI

# Pydantic models
from pydantic_models import (
    AngleMetadata,
    BoundingBox,
    ProductRecord,
    MVVResult,
    VisionFeatures,
    RetrievalResult
)

# LangChain and Vector DB
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document

# Load environment variables
load_dotenv()


class DataProcessor:
    """
    Data processor for Phase 2 operations.

    Handles MongoDB storage, Multi-View Verification,
    and ChromaDB vector database initialization.
    """

    def __init__(
        self,
        mongodb_uri: str = None,
        mongodb_db: str = "product_capture_db",
        mongodb_collection: str = "captures"
    ):
        """
        Initialize the data processor.

        Args:
            mongodb_uri: MongoDB connection URI (from env if not provided)
            mongodb_db: MongoDB database name
            mongodb_collection: MongoDB collection name
        """
        # Initialize MongoDB
        self.mongodb_uri = mongodb_uri or os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
        self.mongodb_db_name = mongodb_db
        self.mongodb_collection_name = mongodb_collection

        self._initialize_mongodb()

        # Initialize embeddings and vector store
        self.embeddings = None
        self.vector_store = None

        print(f"[INFO] DataProcessor initialized with MongoDB")

    def _initialize_mongodb(self) -> None:
        """
        Initialize MongoDB connection and create indexes.
        """
        try:
            # Connect to MongoDB
            self.mongo_client = MongoClient(self.mongodb_uri)

            # Test connection
            self.mongo_client.admin.command('ping')

            # Get database and collection
            self.mongo_db = self.mongo_client[self.mongodb_db_name]
            self.mongo_collection = self.mongo_db[self.mongodb_collection_name]

            # Create indexes
            self.mongo_collection.create_index("session_id", unique=True)
            self.mongo_collection.create_index("created_at")
            self.mongo_collection.create_index("product_id")

            print(f"[INFO] MongoDB connected successfully")
            print(f"[INFO] Database: {self.mongodb_db_name}")
            print(f"[INFO] Collection: {self.mongodb_collection_name}")

        except ConnectionFailure as e:
            raise RuntimeError(f"Failed to connect to MongoDB: {e}")
        except Exception as e:
            raise RuntimeError(f"MongoDB initialization error: {e}")

    def multi_view_verification(
        self,
        angle_metadata_list: List[Dict[str, Any]]
    ) -> MVVResult:

        print(f"[INFO] Running Multi-View Verification on {len(angle_metadata_list)} angles...")

        # Simulate MVV processing
        total_angles = len(angle_metadata_list)

        # Check 1: Tracking ID consistency
        track_ids = [a.get('track_id') for a in angle_metadata_list if a.get('track_id')]
        track_id_consistent = len(set(track_ids)) <= 1 if track_ids else True

        # Check 2: Confidence scores
        confidences = [a.get('confidence', 0.0) for a in angle_metadata_list]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        # Check 3: Bounding box area consistency (should be similar across angles)
        bbox_areas = [a.get('bbox_area', 0.0) for a in angle_metadata_list]
        avg_bbox_area = sum(bbox_areas) / len(bbox_areas) if bbox_areas else 0.0
        bbox_variance = sum((a - avg_bbox_area) ** 2 for a in bbox_areas) / len(bbox_areas) if bbox_areas else 0
        bbox_consistent = bbox_variance < (avg_bbox_area * 0.3)  # 30% tolerance

        # Check 4: All IQA checks passed
        all_iqa_passed = all(a.get('iqa_passed', False) for a in angle_metadata_list)

        # Calculate overall confidence score
        confidence_factors = [
            0.3 if track_id_consistent else 0.0,
            0.3 * avg_confidence,
            0.2 if bbox_consistent else 0.0,
            0.2 if all_iqa_passed else 0.0
        ]
        overall_confidence = sum(confidence_factors)

        # Determine verification status
        verified = overall_confidence >= 0.7  # 70% threshold

        # Generate summary text for RAG
        summary_parts = [
            f"Product captured from {total_angles} different angles.",
            f"Average detection confidence: {avg_confidence:.2f}",
            f"Average object size: {avg_bbox_area:.0f} pixels²",
        ]

        # Add identifying features from each angle
        for i, angle in enumerate(angle_metadata_list, 1):
            angle_summary = (
                f"Angle {i}: "
                f"Confidence {angle.get('confidence', 0.0):.2f}, "
                f"Area {angle.get('bbox_area', 0.0):.0f}px², "
                f"IQA: {'Passed' if angle.get('iqa_passed') else 'Failed'}"
            )
            summary_parts.append(angle_summary)

        summary_text = " ".join(summary_parts)

        # Create angle consistency metrics
        angle_consistency = {
            "track_id_consistent": track_id_consistent,
            "unique_track_ids": len(set(track_ids)) if track_ids else 0,
            "avg_confidence": avg_confidence,
            "bbox_area_variance": bbox_variance,
            "bbox_consistent": bbox_consistent,
            "all_iqa_passed": all_iqa_passed
        }

        verification_reason = (
            "Verification passed: All quality checks satisfied." if verified
            else f"Verification failed: Confidence score {overall_confidence:.2f} below threshold 0.70"
        )

        result = MVVResult(
            confidence_score=overall_confidence,
            summary_text=summary_text,
            angle_consistency=angle_consistency,
            verified=verified,
            verification_reason=verification_reason
        )

        print(f"[INFO] MVV Complete - Verified: {verified}, Confidence: {overall_confidence:.2f}")

        return result

    def extract_features_with_vision(
        self,
        angle_metadata_list: List[AngleMetadata]
    ) -> Optional[VisionFeatures]:
        """
        Extract product features using OpenAI Vision Model (GPT-4o).

        This function performs multimodal analysis by:
        1. Reading captured product images
        2. Encoding them to Base64
        3. Sending them to GPT-4o with a detailed prompt
        4. Parsing the structured JSON response

        Args:
            angle_metadata_list: List of AngleMetadata objects with image paths

        Returns:
            VisionFeatures object or None if extraction fails
        """
        print("[INFO] Starting Vision Model feature extraction...")

        try:
            # Get OpenAI API key
            openai_api_key = os.getenv("OPENAI_API_KEY")
            if not openai_api_key:
                print("[ERROR] OPENAI_API_KEY not set. Skipping vision extraction.")
                return None

            # Initialize OpenAI client
            client = OpenAI(api_key=openai_api_key)

            # Select images to analyze (Angle 1, 2, 3)
            images_to_analyze = []
            for angle_meta in angle_metadata_list[:3]:  # First 3 angles
                image_path = Path(angle_meta.image_path)

                if not image_path.exists():
                    print(f"[WARNING] Image not found: {image_path}")
                    continue

                # Read and encode image to base64
                with open(image_path, "rb") as image_file:
                    image_data = base64.b64encode(image_file.read()).decode('utf-8')
                    images_to_analyze.append({
                        "angle": angle_meta.angle_number,
                        "data": image_data
                    })

            if not images_to_analyze:
                print("[ERROR] No valid images found for vision analysis")
                return None

            print(f"[INFO] Analyzing {len(images_to_analyze)} images with GPT-4o...")

            # Construct the prompt for vision analysis
            system_prompt = """You are an expert product feature extraction specialist.
Your task is to perform a comprehensive synthesis analysis across multiple product images.

Analyze the provided images and extract structured information about the product.

You MUST respond with ONLY a valid JSON object (no markdown, no explanations) with this exact structure:
{
  "product_type": "string describing the product category",
  "dominant_colors": ["color1", "color2", "color3"],
  "material_guess": "estimated material composition",
  "text_found": ["any visible text or labels"],
  "shape_description": "overall shape characteristics",
  "dimensions_estimate": "approximate size description (e.g., small/medium/large)",
  "notable_features": ["distinctive characteristic 1", "distinctive characteristic 2"],
  "condition": "product condition assessment",
  "brand_identified": "any visible brand information or null",
  "additional_details": {"key": "value pairs of other relevant details"}
}

Be specific and descriptive. If information is not visible, use null for strings or [] for arrays."""

            user_prompt = f"Analyze these {len(images_to_analyze)} product images from different angles and extract all identifying features. Provide a comprehensive synthesis."

            # Prepare messages with images
            message_content = [{"type": "text", "text": user_prompt}]

            for img in images_to_analyze:
                message_content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{img['data']}",
                        "detail": "high"
                    }
                })

            # Call OpenAI Vision API
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message_content}
                ],
                max_tokens=1500,
                temperature=0.2  # Lower temperature for more consistent extraction
            )

            # Extract response
            raw_response = response.choices[0].message.content
            print(f"[INFO] Vision Model response received ({len(raw_response)} chars)")

            # Parse JSON response
            try:
                # Clean response if it has markdown formatting
                cleaned_response = raw_response.strip()
                if cleaned_response.startswith("```json"):
                    cleaned_response = cleaned_response[7:]
                if cleaned_response.startswith("```"):
                    cleaned_response = cleaned_response[3:]
                if cleaned_response.endswith("```"):
                    cleaned_response = cleaned_response[:-3]
                cleaned_response = cleaned_response.strip()

                features_dict = json.loads(cleaned_response)

                # Create VisionFeatures object
                vision_features = VisionFeatures(
                    product_type=features_dict.get("product_type"),
                    dominant_colors=features_dict.get("dominant_colors", []),
                    material_guess=features_dict.get("material_guess"),
                    text_found=features_dict.get("text_found", []),
                    shape_description=features_dict.get("shape_description"),
                    dimensions_estimate=features_dict.get("dimensions_estimate"),
                    notable_features=features_dict.get("notable_features", []),
                    condition=features_dict.get("condition"),
                    brand_identified=features_dict.get("brand_identified"),
                    additional_details=features_dict.get("additional_details", {}),
                    raw_response=raw_response
                )

                print("[SUCCESS] Vision features extracted successfully")
                print(f"  Product Type: {vision_features.product_type}")
                print(f"  Colors: {', '.join(vision_features.dominant_colors) if vision_features.dominant_colors else 'N/A'}")
                print(f"  Material: {vision_features.material_guess}")

                return vision_features

            except json.JSONDecodeError as e:
                print(f"[ERROR] Failed to parse Vision Model JSON response: {e}")
                print(f"[DEBUG] Raw response: {raw_response[:500]}...")

                # Check if it's a content policy refusal
                if "sorry" in raw_response.lower() or "can't assist" in raw_response.lower() or "cannot" in raw_response.lower():
                    print("[WARNING] GPT-4o Vision refused to analyze this image (likely content policy)")
                    print("[INFO] Common reasons: people/faces, sensitive documents, unclear images")
                    print("[INFO] Continuing without vision features...")
                    return None

                # Create minimal VisionFeatures with raw response for other parsing errors
                return VisionFeatures(
                    product_type="Unknown (parsing error)",
                    raw_response=raw_response
                )

        except Exception as e:
            print(f"[ERROR] Vision feature extraction failed: {e}")
            import traceback
            traceback.print_exc()
            return None

    def save_product_record(self, product_record: ProductRecord) -> bool:
        """
        Save a product record to MongoDB.

        Args:
            product_record: ProductRecord object to save

        Returns:
            True if saved successfully, False otherwise
        """
        try:
            # Convert to dict
            data = product_record.dict()

            # Insert or update
            self.mongo_collection.update_one(
                {"session_id": product_record.session_id},
                {"$set": data},
                upsert=True
            )

            print(f"[SUCCESS] Product record saved to MongoDB: {product_record.session_id}")
            return True

        except DuplicateKeyError:
            print(f"[WARNING] Duplicate session_id: {product_record.session_id}. Updating existing record.")
            return True

        except Exception as e:
            print(f"[ERROR] MongoDB save failed: {e}")
            return False

    def get_product_record(self, session_id: str) -> Optional[ProductRecord]:
        """
        Retrieve a product record by session ID from MongoDB.

        Args:
            session_id: Session ID to retrieve

        Returns:
            ProductRecord object or None if not found (or if it's Phase 1 raw data)
        """
        try:
            data = self.mongo_collection.find_one({"session_id": session_id})

            if not data:
                return None

            # Check if this is Phase 1 raw data (not processed by Phase 2)
            if 'captured_angles' not in data:
                print(f"[INFO] Session {session_id} has raw Phase 1 data, not yet processed by Phase 2")
                return None

            # Remove MongoDB _id field
            data.pop('_id', None)

            # Reconstruct nested models
            data['captured_angles'] = [AngleMetadata(**a) for a in data['captured_angles']]
            if data.get('mvv_result'):
                data['mvv_result'] = MVVResult(**data['mvv_result'])

            return ProductRecord(**data)

        except Exception as e:
            print(f"[ERROR] Failed to retrieve product record: {e}")
            return None

    def get_all_product_records(self) -> List[ProductRecord]:
        """
        Retrieve all product records from MongoDB.

        Returns:
            List of ProductRecord objects (only those processed by Phase 2)
        """
        try:
            records = []
            for data in self.mongo_collection.find():
                # Skip documents that don't have captured_angles (Phase 1 raw data)
                if 'captured_angles' not in data:
                    continue

                data.pop('_id', None)

                try:
                    data['captured_angles'] = [AngleMetadata(**a) for a in data['captured_angles']]
                    if data.get('mvv_result'):
                        data['mvv_result'] = MVVResult(**data['mvv_result'])
                    records.append(ProductRecord(**data))
                except Exception as e:
                    # Skip malformed records
                    print(f"[WARNING] Skipping malformed record {data.get('session_id', 'unknown')}: {e}")
                    continue

            return records

        except Exception as e:
            print(f"[ERROR] Failed to retrieve all records: {e}")
            return []

    def initialize_vector_store(self) -> bool:
        """
        Initialize ChromaDB vector store with all product records.

        This function:
        1. Retrieves all ProductRecord documents from MongoDB
        2. Generates OpenAI embeddings for each summary_for_rag
        3. Stores embeddings in ChromaDB for RAG retrieval

        Returns:
            True if successful, False otherwise
        """
        try:
            print("[INFO] Initializing vector store...")

            # Initialize OpenAI embeddings
            openai_api_key = os.getenv("OPENAI_API_KEY")
            if not openai_api_key:
                raise ValueError("OPENAI_API_KEY not found in environment variables")

            self.embeddings = OpenAIEmbeddings(
                model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
                openai_api_key=openai_api_key
            )

            # Retrieve all product records
            records = self.get_all_product_records()

            if not records:
                print("[WARNING] No product records found to index")
                return False

            print(f"[INFO] Found {len(records)} product records to index")

            # Convert records to LangChain Documents
            documents = []
            for record in records:
                doc = Document(
                    page_content=record.summary_for_rag,
                    metadata={
                        "session_id": record.session_id,
                        "product_id": record.product_id,
                        "total_angles": record.total_angles,
                        "mvv_confidence": record.mvv_result.confidence_score if record.mvv_result else 0.0,
                        "created_at": record.created_at.isoformat()
                    }
                )
                documents.append(doc)

            # Create ChromaDB vector store (no persist_directory needed in newer versions)
            self.vector_store = Chroma.from_documents(
                documents=documents,
                embedding=self.embeddings,
                collection_name="product_knowledge"
            )

            print(f"[SUCCESS] Vector store initialized with {len(documents)} documents")

            return True

        except Exception as e:
            print(f"[ERROR] Failed to initialize vector store: {e}")
            import traceback
            traceback.print_exc()
            return False

    def get_vector_store(self) -> Optional[Chroma]:
        """
        Get the initialized vector store.

        Returns:
            ChromaDB vector store or None if not initialized
        """
        if self.vector_store is None:
            print("[INFO] Vector store not initialized. Initializing...")

            try:
                openai_api_key = os.getenv("OPENAI_API_KEY")
                if not openai_api_key:
                    raise ValueError("OPENAI_API_KEY not found in environment variables")

                self.embeddings = OpenAIEmbeddings(
                    model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
                    openai_api_key=openai_api_key
                )

                # Try to load existing collection
                self.vector_store = Chroma(
                    collection_name="product_knowledge",
                    embedding_function=self.embeddings
                )

                # Check if collection is empty
                try:
                    count = self.vector_store._collection.count()
                    if count == 0:
                        print("[INFO] Vector store is empty. Checking MongoDB for records...")
                        records = self.get_all_product_records()
                        if records:
                            print(f"[INFO] Found {len(records)} product records in MongoDB. Rebuilding vector store...")
                            self.initialize_vector_store()
                        else:
                            print("[INFO] No product records found in MongoDB")
                    else:
                        print(f"[SUCCESS] Vector store loaded with {count} documents")
                except Exception as e:
                    print(f"[WARNING] Could not check vector store count: {e}")
                    print("[SUCCESS] Vector store loaded")

            except Exception as e:
                print(f"[ERROR] Failed to load vector store: {e}")
                print("[INFO] Initializing new vector store...")
                self.initialize_vector_store()

        return self.vector_store

    def process_session_metadata(
        self,
        metadata_file_path: str,
        product_id: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Optional[ProductRecord]:
        """
        Process a capture session metadata file and save to MongoDB.

        This is the main integration point between Phase 1 and Phase 2.

        Args:
            metadata_file_path: Path to the JSON metadata file from Phase 1
            product_id: Optional product identifier
            notes: Optional notes to attach to the record

        Returns:
            ProductRecord object if successful, None otherwise
        """
        try:
            print(f"[INFO] Processing metadata file: {metadata_file_path}")

            # Load metadata file
            with open(metadata_file_path, 'r') as f:
                session_data = json.load(f)

            # Detect metadata format (three possible formats)
            if 'captures' in session_data and 'session_info' in session_data:
                # NEW Phase 1 format (Dec 2025) - with session_info
                print("[INFO] Detected new Phase 1 metadata format (2025)")
                session_id = session_data['session_id']
                total_angles = session_data['session_info']['total_angles']

                # Convert Phase 1 captures to AngleMetadata format
                angle_metadata_list = []
                for angle_key, capture_data in session_data['captures'].items():
                    # Extract bounding box
                    bbox_data = capture_data['detection']['bounding_box']
                    bbox = {
                        'x1': bbox_data['x1'],
                        'y1': bbox_data['y1'],
                        'x2': bbox_data['x2'],
                        'y2': bbox_data['y2']
                    }

                    # Determine IQA status
                    quality = capture_data['quality_assessment']
                    iqa_passed = quality['overall_status'] in ['good', 'excellent']
                    iqa_reason = '; '.join(quality.get('recommendations', []))

                    angle_metadata = {
                        'angle_number': capture_data['angle_number'],
                        'image_path': capture_data['image']['local_path'],
                        'timestamp': capture_data['timestamp'],
                        'bbox': bbox,
                        'bbox_area': bbox_data['area_pixels'],
                        'track_id': capture_data['detection']['track_id'],
                        'confidence': capture_data['detection']['confidence'],
                        'iqa_passed': iqa_passed,
                        'iqa_reason': iqa_reason or 'No issues detected'
                    }
                    angle_metadata_list.append(angle_metadata)

            elif 'captures' in session_data and isinstance(session_data['captures'], dict):
                # OLD Phase 1 format (Dec 2024) - with captures dict but no session_info
                print("[INFO] Detected old Phase 1 metadata format (2024)")
                session_id = session_data['session_id']
                total_angles = len(session_data['captures'])

                # Convert old Phase 1 captures to AngleMetadata format
                angle_metadata_list = []
                for angle_key, capture_data in session_data['captures'].items():
                    # Extract bounding box (different field names in old format)
                    bbox = capture_data.get('bbox', {})

                    # Determine IQA status from quality field
                    quality_str = capture_data.get('quality', 'WARN')
                    iqa_passed = quality_str in ['OK', 'GOOD', 'EXCELLENT']
                    iqa_reason = '; '.join(capture_data.get('recommendations', []))

                    angle_metadata = {
                        'angle_number': capture_data['angle_number'],
                        'image_path': capture_data.get('local_path', capture_data.get('image_filename', '')),
                        'timestamp': capture_data['timestamp'],
                        'bbox': bbox,
                        'bbox_area': capture_data.get('bbox_area', 0),
                        'track_id': capture_data.get('track_id'),
                        'confidence': capture_data.get('confidence', 0.0),
                        'iqa_passed': iqa_passed,
                        'iqa_reason': iqa_reason or 'No issues detected'
                    }
                    angle_metadata_list.append(angle_metadata)

            else:
                # Phase 2 format (with metadata list)
                print("[INFO] Detected Phase 2 metadata format")
                session_id = session_data['session_id']
                total_angles = session_data['total_angles']
                angle_metadata_list = session_data['metadata']

            # Convert to AngleMetadata objects
            captured_angles = []
            for angle_data in angle_metadata_list:
                # Convert bbox dict to BoundingBox
                angle_data['bbox'] = BoundingBox(**angle_data['bbox'])
                captured_angles.append(AngleMetadata(**angle_data))

            # Run Multi-View Verification
            mvv_result = self.multi_view_verification(angle_metadata_list)

            # Extract features using Vision Model (GPT-4o)
            print("\n" + "="*60)
            print("VISION MODEL FEATURE EXTRACTION")
            print("="*60)

            vision_features = self.extract_features_with_vision(captured_angles)

            # Integrate vision features into MVV result
            if vision_features:
                mvv_result.vision_features = vision_features
                print("[INFO] Vision features integrated into MVV result")
            else:
                print("[WARNING] No vision features extracted (will proceed without them)")

            print("="*60 + "\n")

            # Create enhanced summary for RAG
            summary_for_rag = mvv_result.summary_text

            # Enhance RAG summary with vision features
            if vision_features:
                vision_summary_parts = []

                if vision_features.product_type:
                    vision_summary_parts.append(f"Product Type: {vision_features.product_type}.")

                if vision_features.dominant_colors:
                    colors = ", ".join(vision_features.dominant_colors)
                    vision_summary_parts.append(f"Colors: {colors}.")

                if vision_features.material_guess:
                    vision_summary_parts.append(f"Material: {vision_features.material_guess}.")

                if vision_features.shape_description:
                    vision_summary_parts.append(f"Shape: {vision_features.shape_description}.")

                if vision_features.dimensions_estimate:
                    vision_summary_parts.append(f"Size: {vision_features.dimensions_estimate}.")

                if vision_features.notable_features:
                    features = ", ".join(vision_features.notable_features)
                    vision_summary_parts.append(f"Notable Features: {features}.")

                if vision_features.text_found:
                    text = ", ".join(vision_features.text_found)
                    vision_summary_parts.append(f"Visible Text: {text}.")

                if vision_features.brand_identified:
                    vision_summary_parts.append(f"Brand: {vision_features.brand_identified}.")

                if vision_features.condition:
                    vision_summary_parts.append(f"Condition: {vision_features.condition}.")

                # Append vision summary to RAG summary
                if vision_summary_parts:
                    vision_summary = " ".join(vision_summary_parts)
                    summary_for_rag = f"{summary_for_rag} VISUAL ANALYSIS: {vision_summary}"

                    print(f"[INFO] Enhanced RAG summary with {len(vision_summary_parts)} vision attributes")

            # Determine output directory from first image path
            if captured_angles:
                output_directory = str(Path(captured_angles[0].image_path).parent)
            else:
                output_directory = "unknown"

            # Create ProductRecord
            product_record = ProductRecord(
                session_id=session_id,
                product_id=product_id,
                total_angles=total_angles,
                captured_angles=captured_angles,
                mvv_result=mvv_result,
                summary_for_rag=summary_for_rag,
                output_directory=output_directory,
                notes=notes
            )

            # Save to MongoDB
            if self.save_product_record(product_record):
                print(f"[SUCCESS] Session {session_id} processed and saved to MongoDB")
                return product_record
            else:
                print(f"[ERROR] Failed to save session {session_id}")
                return None

        except Exception as e:
            print(f"[ERROR] Failed to process session metadata: {e}")
            import traceback
            traceback.print_exc()
            return None

    def close(self) -> None:
        """Close MongoDB connection."""
        if hasattr(self, 'mongo_client'):
            self.mongo_client.close()
            print("[INFO] MongoDB connection closed")
