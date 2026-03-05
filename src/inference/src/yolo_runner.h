/**
 * YOLO Runner - C++ wrapper for LibTorch inference
 */

#ifndef __YOLO_RUNNER_H__
#define __YOLO_RUNNER_H__

#include <stddef.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Opaque handle to YOLO runner */
typedef void* YoloRunnerHandle;

/**
 * Create YOLO runner and load model
 *
 * @param model_path Path to TorchScript model file
 * @return Handle to YOLO runner, or NULL on failure
 */
YoloRunnerHandle yolo_runner_create(const char* model_path);

/**
 * Run YOLO inference on frame
 *
 * @param handle YOLO runner handle
 * @param data Frame data (RGB or BGR)
 * @param width Frame width
 * @param height Frame height
 * @param confidence Confidence threshold
 * @param annotate Whether to draw on frame
 * @return true on success, false on failure
 */
bool yolo_runner_infer(YoloRunnerHandle handle,
                       unsigned char* data,
                       int width,
                       int height,
                       float confidence,
                       bool annotate);

/**
 * Destroy YOLO runner and free resources
 *
 * @param handle YOLO runner handle
 */
void yolo_runner_destroy(YoloRunnerHandle handle);

#ifdef __cplusplus
}
#endif

#endif /* __YOLO_RUNNER_H__ */
