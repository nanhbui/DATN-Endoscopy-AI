#!/usr/bin/env python3
"""
Export YOLOv8 model to TorchScript format for C++ plugin
"""
from ultralytics import YOLO
import sys

def export_model(model_path, output_name=None):
    """Export YOLO model to TorchScript"""
    print("="*60)
    print("Exporting YOLO Model to TorchScript")
    print("="*60)

    print(f"\n[1/3] Loading model: {model_path}")
    try:
        model = YOLO(model_path)
        print(f"✅ Model loaded successfully")
    except Exception as e:
        print(f"❌ Failed to load model: {e}")
        return False

    print(f"\n[2/3] Exporting to TorchScript...")
    try:
        # Export to TorchScript
        export_path = model.export(format='torchscript', imgsz=640)
        print(f"✅ Export successful!")
        print(f"   Output: {export_path}")
    except Exception as e:
        print(f"❌ Export failed: {e}")
        return False

    print(f"\n[3/3] Verifying export...")
    import torch
    try:
        # Load and verify
        ts_model = torch.jit.load(export_path)
        print(f"✅ TorchScript model verified")

        # Test inference with dummy input
        dummy_input = torch.randn(1, 3, 640, 640)
        with torch.no_grad():
            output = ts_model(dummy_input)
        print(f"✅ Test inference successful")

        # Print output info
        if isinstance(output, tuple):
            print(f"   Output: tuple with {len(output)} elements")
            for i, o in enumerate(output):
                if isinstance(o, torch.Tensor):
                    print(f"   Output[{i}]: shape={o.shape}, dtype={o.dtype}")
        elif isinstance(output, torch.Tensor):
            print(f"   Output: shape={output.shape}, dtype={output.dtype}")

    except Exception as e:
        print(f"❌ Verification failed: {e}")
        return False

    print("\n" + "="*60)
    print("✅ EXPORT COMPLETE")
    print("="*60)
    print(f"\nTorchScript model: {export_path}")
    print(f"\nYou can now use this model with the C++ plugin:")
    print(f"  yoloinference model={export_path}")

    return True

if __name__ == '__main__':
    model_path = 'yolov8n-seg.pt'

    if len(sys.argv) > 1:
        model_path = sys.argv[1]

    success = export_model(model_path)
    sys.exit(0 if success else 1)
