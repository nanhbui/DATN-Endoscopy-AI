/**
 * YOLO Runner Implementation using LibTorch
 */

#include "yolo_runner.h"

#include <torch/script.h>
#include <torch/torch.h>
#include <opencv2/opencv.hpp>

#include <iostream>
#include <memory>
#include <vector>
#include <algorithm>

// Detection structure
struct Detection {
    cv::Rect bbox;
    float confidence;
    int class_id;
    cv::Mat mask;
};

// NMS helper function
std::vector<int> non_max_suppression(
    const std::vector<cv::Rect>& boxes,
    const std::vector<float>& scores,
    float iou_threshold) {

    std::vector<int> indices(boxes.size());
    std::iota(indices.begin(), indices.end(), 0);

    // Sort by scores descending
    std::sort(indices.begin(), indices.end(), [&scores](int i1, int i2) {
        return scores[i1] > scores[i2];
    });

    std::vector<int> keep;
    std::vector<bool> suppressed(boxes.size(), false);

    for (size_t i = 0; i < indices.size(); ++i) {
        int idx = indices[i];
        if (suppressed[idx]) continue;

        keep.push_back(idx);

        cv::Rect box1 = boxes[idx];

        for (size_t j = i + 1; j < indices.size(); ++j) {
            int idx2 = indices[j];
            if (suppressed[idx2]) continue;

            cv::Rect box2 = boxes[idx2];

            // Calculate IoU
            cv::Rect intersect = box1 & box2;
            float intersection = intersect.area();
            float union_area = box1.area() + box2.area() - intersection;

            if (union_area > 0) {
                float iou = intersection / union_area;
                if (iou > iou_threshold) {
                    suppressed[idx2] = true;
                }
            }
        }
    }

    return keep;
}

class YoloRunner {
public:
    YoloRunner(const std::string& model_path)
        : device_(torch::kCPU) {  // Initialize device in initializer list
        try {
            // Load TorchScript model
            module_ = torch::jit::load(model_path);
            module_.eval();

            // Set device (CPU or CUDA)
            if (torch::cuda::is_available()) {
                device_ = torch::Device(torch::kCUDA);
                std::cout << "[INFO] Using CUDA device" << std::endl;
            } else {
                device_ = torch::Device(torch::kCPU);
                std::cout << "[INFO] Using CPU device" << std::endl;
            }

            module_.to(device_);

            std::cout << "[SUCCESS] YOLO model loaded: " << model_path << std::endl;
        } catch (const c10::Error& e) {
            std::cerr << "[ERROR] Failed to load model: " << e.what() << std::endl;
            throw;
        }
    }

    bool infer(unsigned char* data, int width, int height,
               float confidence, bool annotate) {
        try {
            // Convert raw data to cv::Mat (assuming RGB format)
            cv::Mat frame(height, width, CV_8UC3, data);

            // Preprocess: resize to 640x640 and normalize
            cv::Mat resized;
            cv::resize(frame, resized, cv::Size(640, 640));

            // Convert to float and normalize [0, 1]
            resized.convertTo(resized, CV_32FC3, 1.0 / 255.0);

            // Convert to tensor [1, 3, 640, 640]
            torch::Tensor tensor = torch::from_blob(
                resized.data,
                {1, resized.rows, resized.cols, 3},
                torch::kFloat32
            ).clone().to(device_);

            // Permute to [1, 3, 640, 640] (channels first)
            tensor = tensor.permute({0, 3, 1, 2}).contiguous();

            // Run inference
            std::vector<torch::jit::IValue> inputs;
            inputs.push_back(tensor);

            auto output = module_.forward(inputs).toTuple();

            // Parse YOLOv8-seg output
            // Output[0]: [1, 116, 8400] - detections (4 bbox + 80 classes + 32 mask coeffs)
            // Output[1]: [1, 32, 160, 160] - mask prototypes
            auto detections = output->elements()[0].toTensor().to(torch::kCPU);
            torch::Tensor mask_protos;

            if (output->elements().size() > 1) {
                mask_protos = output->elements()[1].toTensor().to(torch::kCPU);
            }

            // Parse detections
            std::vector<Detection> dets = parseDetections(
                detections, mask_protos, confidence, 0.45f, width, height);

            if (annotate && !dets.empty()) {
                drawDetections(frame, dets);
            }

            return true;

        } catch (const c10::Error& e) {
            std::cerr << "[ERROR] Inference failed: " << e.what() << std::endl;
            return false;
        } catch (const std::exception& e) {
            std::cerr << "[ERROR] Exception during inference: " << e.what() << std::endl;
            return false;
        }
    }

private:
    torch::jit::script::Module module_;
    torch::Device device_;

    std::vector<Detection> parseDetections(
        torch::Tensor detections,
        torch::Tensor mask_protos,
        float conf_threshold,
        float iou_threshold,
        int orig_width,
        int orig_height) {

        std::vector<Detection> results;

        // detections shape: [1, 116, 8400]
        // Transpose to [8400, 116]
        detections = detections.squeeze(0).transpose(0, 1);

        std::vector<cv::Rect> boxes;
        std::vector<float> scores;
        std::vector<int> class_ids;
        std::vector<std::vector<float>> mask_coeffs;

        auto det_accessor = detections.accessor<float, 2>();
        int num_detections = detections.size(0);

        // Parse each detection
        for (int i = 0; i < num_detections; ++i) {
            // Extract class scores (indices 4-83)
            float max_score = 0.0f;
            int max_class = 0;

            for (int c = 0; c < 80; ++c) {
                float score = det_accessor[i][4 + c];
                if (score > max_score) {
                    max_score = score;
                    max_class = c;
                }
            }

            // Filter by confidence
            if (max_score < conf_threshold) continue;

            // Extract bbox (cx, cy, w, h) - indices 0-3
            float cx = det_accessor[i][0];
            float cy = det_accessor[i][1];
            float w = det_accessor[i][2];
            float h = det_accessor[i][3];

            // Convert to (x1, y1, x2, y2) and scale to original image size
            float x1 = (cx - w / 2.0f) * orig_width / 640.0f;
            float y1 = (cy - h / 2.0f) * orig_height / 640.0f;
            float x2 = (cx + w / 2.0f) * orig_width / 640.0f;
            float y2 = (cy + h / 2.0f) * orig_height / 640.0f;

            // Clamp to image bounds
            x1 = std::max(0.0f, std::min(x1, (float)orig_width));
            y1 = std::max(0.0f, std::min(y1, (float)orig_height));
            x2 = std::max(0.0f, std::min(x2, (float)orig_width));
            y2 = std::max(0.0f, std::min(y2, (float)orig_height));

            cv::Rect bbox(x1, y1, x2 - x1, y2 - y1);

            boxes.push_back(bbox);
            scores.push_back(max_score);
            class_ids.push_back(max_class);

            // Extract mask coefficients (indices 84-115)
            std::vector<float> coeffs;
            for (int k = 84; k < 116; ++k) {
                coeffs.push_back(det_accessor[i][k]);
            }
            mask_coeffs.push_back(coeffs);
        }

        // Apply NMS
        std::vector<int> keep_indices = non_max_suppression(boxes, scores, iou_threshold);

        // Create final detections
        for (int idx : keep_indices) {
            Detection det;
            det.bbox = boxes[idx];
            det.confidence = scores[idx];
            det.class_id = class_ids[idx];

            // Generate mask if prototypes available
            if (mask_protos.defined() && mask_protos.numel() > 0) {
                det.mask = generateMask(mask_protos, mask_coeffs[idx],
                                       det.bbox, orig_width, orig_height);
            }

            results.push_back(det);
        }

        return results;
    }

    cv::Mat generateMask(
        torch::Tensor mask_protos,
        const std::vector<float>& coeffs,
        const cv::Rect& bbox,
        int orig_width,
        int orig_height) {

        try {
            // mask_protos: [1, 32, 160, 160]
            mask_protos = mask_protos.squeeze(0);  // [32, 160, 160]

            // Convert coefficients to tensor
            torch::Tensor coeff_tensor = torch::from_blob(
                const_cast<float*>(coeffs.data()),
                {32},
                torch::kFloat32
            ).clone();

            // Matrix multiply: [32] @ [32, 160, 160] -> [160, 160]
            auto mask_160 = torch::einsum("c,chw->hw", {coeff_tensor, mask_protos});

            // Sigmoid activation
            mask_160 = torch::sigmoid(mask_160);

            // Resize to original image size
            mask_160 = mask_160.unsqueeze(0).unsqueeze(0);  // [1, 1, 160, 160]
            auto mask_full = torch::nn::functional::interpolate(
                mask_160,
                torch::nn::functional::InterpolateFuncOptions()
                    .size(std::vector<int64_t>{orig_height, orig_width})
                    .mode(torch::kBilinear)
                    .align_corners(false)
            );

            mask_full = mask_full.squeeze(0).squeeze(0);  // [orig_height, orig_width]

            // Crop to bbox
            int x1 = std::max(0, bbox.x);
            int y1 = std::max(0, bbox.y);
            int x2 = std::min(orig_width, bbox.x + bbox.width);
            int y2 = std::min(orig_height, bbox.y + bbox.height);

            if (x2 <= x1 || y2 <= y1) {
                return cv::Mat();
            }

            auto mask_crop = mask_full.index({
                torch::indexing::Slice(y1, y2),
                torch::indexing::Slice(x1, x2)
            });

            // Convert to OpenCV Mat
            mask_crop = (mask_crop * 255).to(torch::kU8).to(torch::kCPU);
            cv::Mat mask_cv(mask_crop.size(0), mask_crop.size(1), CV_8UC1,
                           mask_crop.data_ptr<uint8_t>());

            return mask_cv.clone();

        } catch (const std::exception& e) {
            std::cerr << "[WARN] Mask generation failed: " << e.what() << std::endl;
            return cv::Mat();
        }
    }

    void drawDetections(cv::Mat& frame, const std::vector<Detection>& detections) {
        for (const auto& det : detections) {
            // Draw bounding box
            cv::rectangle(frame, det.bbox, cv::Scalar(0, 255, 0), 2);

            // Note: Text drawing disabled due to ABI incompatibility between PyTorch (old ABI)
            // and system OpenCV (new ABI). Bounding boxes and masks still work!

            // Draw mask contour if available
            if (!det.mask.empty()) {
                cv::Mat mask_binary;
                cv::threshold(det.mask, mask_binary, 127, 255, cv::THRESH_BINARY);

                std::vector<std::vector<cv::Point>> contours;
                cv::findContours(mask_binary, contours, cv::RETR_EXTERNAL,
                                cv::CHAIN_APPROX_SIMPLE);

                // Draw contours on the bbox region
                cv::Mat roi = frame(det.bbox);
                cv::drawContours(roi, contours, -1, cv::Scalar(0, 255, 0), 2);
            }
        }
    }
};

/* C API implementation */

extern "C" {

YoloRunnerHandle yolo_runner_create(const char* model_path) {
    try {
        YoloRunner* runner = new YoloRunner(model_path);
        return static_cast<YoloRunnerHandle>(runner);
    } catch (...) {
        return nullptr;
    }
}

bool yolo_runner_infer(YoloRunnerHandle handle,
                       unsigned char* data,
                       int width,
                       int height,
                       float confidence,
                       bool annotate) {
    if (!handle) {
        return false;
    }

    YoloRunner* runner = static_cast<YoloRunner*>(handle);
    return runner->infer(data, width, height, confidence, annotate);
}

void yolo_runner_destroy(YoloRunnerHandle handle) {
    if (handle) {
        YoloRunner* runner = static_cast<YoloRunner*>(handle);
        delete runner;
    }
}

} // extern "C"
