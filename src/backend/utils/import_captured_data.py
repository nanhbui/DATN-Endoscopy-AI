#!/usr/bin/env python3
"""
Import captured image data from local folder to MongoDB
"""

import json
import pymongo
from pathlib import Path
from datetime import datetime

def import_session_to_mongodb(session_dir: Path, mongo_uri: str = "mongodb://localhost:27017/"):
    """Import a capture session from local folder to MongoDB"""
    
    metadata_file = session_dir / "metadata.json"
    if not metadata_file.exists():
        print(f"[ERROR] No metadata.json found in {session_dir}")
        return False
    
    try:
        # Read metadata
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)
        
        print(f"[INFO] Found session: {metadata['session_id']}")
        print(f"[INFO] Status: {metadata['session_info']['status']}")
        print(f"[INFO] Captured: {metadata['session_info']['captured_count']}/{metadata['session_info']['total_angles']} angles")
        
        # Connect to MongoDB
        client = pymongo.MongoClient(mongo_uri, serverSelectionTimeoutMS=2000)
        client.server_info()  # Test connection
        
        db = client["product_capture_db"]
        collection = db["captures"]
        
        # Update paths to be absolute
        for angle_key, angle_data in metadata["captures"].items():
            if "image" in angle_data and "local_path" in angle_data["image"]:
                # Convert relative path to absolute
                rel_path = angle_data["image"]["local_path"]
                abs_path = str(session_dir / rel_path.split('/')[-1])
                angle_data["image"]["local_path"] = abs_path
                
                # Same for mask file
                if angle_data["image"].get("mask_file"):
                    mask_filename = angle_data["image"]["mask_file"]
                    angle_data["image"]["mask_file_path"] = str(session_dir / mask_filename)
        
        # Add import timestamp
        metadata["imported_to_mongodb"] = datetime.now().isoformat()
        metadata["metadata_file_path"] = str(metadata_file)
        
        # Upsert to MongoDB
        result = collection.update_one(
            {"session_id": metadata["session_id"]},
            {"$set": metadata},
            upsert=True
        )
        
        if result.upserted_id:
            print(f"[SUCCESS] ✅ Session {metadata['session_id']} imported to MongoDB (new document)")
        else:
            print(f"[SUCCESS] ✅ Session {metadata['session_id']} updated in MongoDB (existing document)")
            
        # Verify the data
        doc = collection.find_one({"session_id": metadata["session_id"]})
        if doc:
            print(f"[VERIFY] Document found with {len(doc['captures'])} captured angles")
            return True
        else:
            print(f"[ERROR] Failed to verify document in MongoDB")
            return False
            
    except Exception as e:
        print(f"[ERROR] Failed to import session: {e}")
        return False

def main():
    """Import all captured sessions to MongoDB"""
    
    # Look for captured_images directories
    search_paths = [
        Path("captured_images"),
        Path("captured_images"),
        Path("./captured_images"),
        Path("./captured_images")
    ]
    
    imported_count = 0
    
    for search_path in search_paths:
        if search_path.exists():
            print(f"[INFO] Searching in: {search_path.absolute()}")
            
            # Find all session directories (timestamp format)
            for session_dir in search_path.iterdir():
                if session_dir.is_dir() and len(session_dir.name) == 15:  # YYYYMMDD_HHMMSS format
                    print(f"\n[INFO] Processing session directory: {session_dir.name}")
                    if import_session_to_mongodb(session_dir):
                        imported_count += 1
                    else:
                        print(f"[WARNING] Failed to import {session_dir.name}")
    
    if imported_count > 0:
        print(f"\n[SUCCESS] 🎉 Successfully imported {imported_count} session(s) to MongoDB!")
        print(f"[INFO] Database: product_capture_db")
        print(f"[INFO] Collection: captures")
        
        # Test phase_2 compatibility
        try:
            client = pymongo.MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=2000)
            db = client["product_capture_db"]
            collection = db["captures"]
            
            sessions = list(collection.find())
            print(f"\n[VERIFY] MongoDB contains {len(sessions)} session(s):")
            for session in sessions:
                print(f"  - {session['session_id']}: {len(session['captures'])} angles")
                
        except Exception as e:
            print(f"[WARNING] Could not verify MongoDB data: {e}")
    else:
        print(f"\n[WARNING] No sessions were imported. Check if captured_images directory exists and contains valid sessions.")

if __name__ == "__main__":
    main()