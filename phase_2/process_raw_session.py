#!/usr/bin/env python3
"""
Script to process raw MongoDB sessions into ProductRecord format
for Phase 2 RAG system compatibility
"""
import sys
import os
from pathlib import Path

# Add phase_2 to path 
sys.path.insert(0, str(Path(__file__).parent))

from data_processor import DataProcessor
from pydantic_models import AngleMetadata, BoundingBox, ProductRecord, MVVResult

def process_raw_session_from_mongodb(session_id: str) -> bool:
    """
    Process a raw MongoDB session into ProductRecord format.
    
    Args:
        session_id: The session ID to process
        
    Returns:
        True if successful, False otherwise
    """
    processor = DataProcessor()
    
    try:
        # Get raw session from MongoDB
        raw_session = processor.mongo_collection.find_one({"session_id": session_id})
        
        if not raw_session:
            print(f"❌ Session {session_id} not found")
            return False
            
        print(f"📥 Found session: {session_id}")
        
        # Check if already processed (has product_id field)
        if 'product_id' in raw_session and raw_session['product_id']:
            print(f"✅ Session already processed as ProductRecord")
            return True
            
        # Process raw captures into AngleMetadata format
        angle_metadata_list = []
        captures = raw_session.get('captures', {})
        
        if not captures:
            print(f"❌ No captures found in session")
            return False
            
        print(f"📸 Processing {len(captures)} captures...")
        
        for angle_key, capture_data in captures.items():
            # Extract detection info
            detection = capture_data.get('detection', {})
            bbox_data = detection.get('bounding_box', {})
            
            # Create BoundingBox
            bbox = {
                'x1': bbox_data.get('x1', 0),
                'y1': bbox_data.get('y1', 0), 
                'x2': bbox_data.get('x2', 100),
                'y2': bbox_data.get('y2', 100)
            }
            
            # Quality assessment
            quality = capture_data.get('quality_assessment', {})
            overall_status = quality.get('overall_status', 'unknown')
            iqa_passed = overall_status.lower() in ['good', 'excellent', 'ok']
            
            warnings = quality.get('warnings', [])
            recommendations = quality.get('recommendations', [])
            iqa_reason = '; '.join(warnings + recommendations) if warnings or recommendations else 'No issues detected'
            
            # Image path - adjust relative path
            image_info = capture_data.get('image', {})
            local_path = image_info.get('local_path', '')
            if local_path and not local_path.startswith('phase_1/'):
                local_path = f"phase_1/{local_path}"
            
            angle_metadata = {
                'angle_number': capture_data.get('angle_number', int(angle_key)),
                'image_path': local_path,
                'timestamp': capture_data.get('timestamp', ''),
                'bbox': bbox,
                'bbox_area': bbox_data.get('area_pixels', 0),
                'track_id': detection.get('track_id'),
                'confidence': detection.get('confidence', 0.0),
                'iqa_passed': iqa_passed,
                'iqa_reason': iqa_reason
            }
            
            angle_metadata_list.append(angle_metadata)
            print(f"  ✅ Angle {angle_key}: confidence={detection.get('confidence', 0):.1f}%, quality={overall_status}")
        
        # Convert to AngleMetadata objects
        captured_angles = []
        for angle_data in angle_metadata_list:
            angle_data['bbox'] = BoundingBox(**angle_data['bbox'])
            captured_angles.append(AngleMetadata(**angle_data))
        
        print(f"🔄 Running Multi-View Verification...")
        
        # Run Multi-View Verification
        mvv_result = processor.multi_view_verification(angle_metadata_list)
        
        print(f"🧠 Extracting vision features...")
        
        # Extract features using Vision Model
        vision_features = processor.extract_features_with_vision(captured_angles)
        
        if vision_features:
            mvv_result.vision_features = vision_features
            print("✅ Vision features extracted and integrated")
        
        # Create enhanced RAG summary 
        summary_for_rag = mvv_result.summary_text
        
        if vision_features:
            vision_parts = []
            if vision_features.product_type:
                vision_parts.append(f"Product Type: {vision_features.product_type}")
            if vision_features.dominant_colors:
                vision_parts.append(f"Colors: {', '.join(vision_features.dominant_colors)}")
            if vision_features.material_guess:
                vision_parts.append(f"Material: {vision_features.material_guess}")
            if vision_features.shape_description:
                vision_parts.append(f"Shape: {vision_features.shape_description}")
            if vision_features.notable_features:
                vision_parts.append(f"Features: {', '.join(vision_features.notable_features)}")
            if vision_features.text_found:
                vision_parts.append(f"Text: {', '.join(vision_features.text_found)}")
            if vision_features.brand_identified:
                vision_parts.append(f"Brand: {vision_features.brand_identified}")
            
            if vision_parts:
                vision_summary = ". ".join(vision_parts)
                summary_for_rag = f"{summary_for_rag} VISUAL ANALYSIS: {vision_summary}."
        
        # Generate product ID based on session info
        product_id = f"PRODUCT_{session_id}"
        
        # Determine output directory
        if captured_angles and captured_angles[0].image_path:
            output_directory = str(Path(captured_angles[0].image_path).parent)
        else:
            output_directory = f"phase_1/captured_images/{session_id}"
        
        # Create ProductRecord
        product_record = ProductRecord(
            session_id=session_id,
            product_id=product_id,
            total_angles=len(captured_angles),
            captured_angles=captured_angles,
            mvv_result=mvv_result,
            summary_for_rag=summary_for_rag,
            output_directory=output_directory,
            notes=f"Processed from GStreamer capture session"
        )
        
        print(f"💾 Saving ProductRecord to MongoDB...")
        
        # Save to MongoDB (this will overwrite the raw session with processed version)
        if processor.save_product_record(product_record):
            print(f"✅ Session {session_id} successfully processed into ProductRecord format!")
            print(f"📋 Product ID: {product_id}")
            print(f"📝 RAG Summary: {summary_for_rag[:100]}...")
            return True
        else:
            print(f"❌ Failed to save ProductRecord")
            return False
            
    except Exception as e:
        print(f"❌ Error processing session: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        processor.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python process_raw_session.py <session_id>")
        sys.exit(1)
    
    session_id = sys.argv[1]
    success = process_raw_session_from_mongodb(session_id)
    
    if success:
        print(f"\n🎉 SUCCESS! Session {session_id} is now compatible with Phase 2 RAG system")
        sys.exit(0)
    else:
        print(f"\n💥 FAILED! Could not process session {session_id}")
        sys.exit(1)