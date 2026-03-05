/**
 * GStreamer YOLO Inference Plugin - Main Implementation
 */

#include "gstyoloinference.h"
#include "yolo_runner.h"

#include <gst/gst.h>
#include <gst/video/video.h>
#include <string.h>

GST_DEBUG_CATEGORY_STATIC (gst_yolo_inference_debug);
#define GST_CAT_DEFAULT gst_yolo_inference_debug

/* Properties */
enum
{
  PROP_0,
  PROP_MODEL_PATH,
  PROP_CONFIDENCE,
  PROP_IOU_THRESHOLD,
  PROP_ANNOTATE,
  PROP_EMIT_METADATA
};

/* Default property values */
#define DEFAULT_MODEL_PATH "yolov8n.torchscript"
#define DEFAULT_CONFIDENCE 0.25
#define DEFAULT_IOU_THRESHOLD 0.45
#define DEFAULT_ANNOTATE TRUE
#define DEFAULT_EMIT_METADATA TRUE

/* Pad templates */
static GstStaticPadTemplate sink_template = GST_STATIC_PAD_TEMPLATE ("sink",
    GST_PAD_SINK,
    GST_PAD_ALWAYS,
    GST_STATIC_CAPS (GST_VIDEO_CAPS_MAKE ("{ RGB, BGR }"))
    );

static GstStaticPadTemplate src_template = GST_STATIC_PAD_TEMPLATE ("src",
    GST_PAD_SRC,
    GST_PAD_ALWAYS,
    GST_STATIC_CAPS (GST_VIDEO_CAPS_MAKE ("{ RGB, BGR }"))
    );

#define gst_yolo_inference_parent_class parent_class
G_DEFINE_TYPE (GstYoloInference, gst_yolo_inference, GST_TYPE_BASE_TRANSFORM);

/* Function declarations */
static void gst_yolo_inference_set_property (GObject * object, guint prop_id,
    const GValue * value, GParamSpec * pspec);
static void gst_yolo_inference_get_property (GObject * object, guint prop_id,
    GValue * value, GParamSpec * pspec);
static void gst_yolo_inference_finalize (GObject * object);
static gboolean gst_yolo_inference_start (GstBaseTransform * trans);
static gboolean gst_yolo_inference_stop (GstBaseTransform * trans);
static GstFlowReturn gst_yolo_inference_transform_ip (GstBaseTransform * trans,
    GstBuffer * buf);

/* Class initialization */
static void
gst_yolo_inference_class_init (GstYoloInferenceClass * klass)
{
  GObjectClass *gobject_class = G_OBJECT_CLASS (klass);
  GstElementClass *gstelement_class = GST_ELEMENT_CLASS (klass);
  GstBaseTransformClass *transform_class = GST_BASE_TRANSFORM_CLASS (klass);

  gobject_class->set_property = gst_yolo_inference_set_property;
  gobject_class->get_property = gst_yolo_inference_get_property;
  gobject_class->finalize = gst_yolo_inference_finalize;

  g_object_class_install_property (gobject_class, PROP_MODEL_PATH,
      g_param_spec_string ("model", "Model Path",
          "Path to YOLO TorchScript model file",
          DEFAULT_MODEL_PATH, (GParamFlags)(G_PARAM_READWRITE | G_PARAM_STATIC_STRINGS)));

  g_object_class_install_property (gobject_class, PROP_CONFIDENCE,
      g_param_spec_float ("confidence", "Confidence Threshold",
          "Minimum confidence for detections",
          0.0, 1.0, DEFAULT_CONFIDENCE, (GParamFlags)(G_PARAM_READWRITE | G_PARAM_STATIC_STRINGS)));

  g_object_class_install_property (gobject_class, PROP_IOU_THRESHOLD,
      g_param_spec_float ("iou", "IOU Threshold",
          "IOU threshold for NMS",
          0.0, 1.0, DEFAULT_IOU_THRESHOLD, (GParamFlags)(G_PARAM_READWRITE | G_PARAM_STATIC_STRINGS)));

  g_object_class_install_property (gobject_class, PROP_ANNOTATE,
      g_param_spec_boolean ("annotate", "Annotate",
          "Draw bounding boxes on output frames",
          DEFAULT_ANNOTATE, (GParamFlags)(G_PARAM_READWRITE | G_PARAM_STATIC_STRINGS)));

  g_object_class_install_property (gobject_class, PROP_EMIT_METADATA,
      g_param_spec_boolean ("emit-metadata", "Emit Metadata",
          "Emit detection metadata as GStreamer messages",
          DEFAULT_EMIT_METADATA, (GParamFlags)(G_PARAM_READWRITE | G_PARAM_STATIC_STRINGS)));

  gst_element_class_set_static_metadata (gstelement_class,
      "YOLO Inference",
      "Filter/Analyzer/Video",
      "Performs YOLO object detection and segmentation on video frames",
      "Product Capture System <noreply@example.com>");

  gst_element_class_add_static_pad_template (gstelement_class, &src_template);
  gst_element_class_add_static_pad_template (gstelement_class, &sink_template);

  transform_class->start = GST_DEBUG_FUNCPTR (gst_yolo_inference_start);
  transform_class->stop = GST_DEBUG_FUNCPTR (gst_yolo_inference_stop);
  transform_class->transform_ip = GST_DEBUG_FUNCPTR (gst_yolo_inference_transform_ip);

  GST_DEBUG_CATEGORY_INIT (gst_yolo_inference_debug, "yoloinference", 0,
      "YOLO Inference Element");
}

/* Instance initialization */
static void
gst_yolo_inference_init (GstYoloInference * filter)
{
  filter->model_path = g_strdup (DEFAULT_MODEL_PATH);
  filter->confidence = DEFAULT_CONFIDENCE;
  filter->iou_threshold = DEFAULT_IOU_THRESHOLD;
  filter->annotate = DEFAULT_ANNOTATE;
  filter->emit_metadata = DEFAULT_EMIT_METADATA;

  filter->yolo_runner = NULL;
  filter->frame_count = 0;
  filter->total_inference_time = 0.0;

  gst_base_transform_set_in_place (GST_BASE_TRANSFORM (filter), TRUE);
}

/* Property setters/getters */
static void
gst_yolo_inference_set_property (GObject * object, guint prop_id,
    const GValue * value, GParamSpec * pspec)
{
  GstYoloInference *filter = GST_YOLO_INFERENCE (object);

  switch (prop_id) {
    case PROP_MODEL_PATH:
      g_free (filter->model_path);
      filter->model_path = g_value_dup_string (value);
      break;
    case PROP_CONFIDENCE:
      filter->confidence = g_value_get_float (value);
      break;
    case PROP_IOU_THRESHOLD:
      filter->iou_threshold = g_value_get_float (value);
      break;
    case PROP_ANNOTATE:
      filter->annotate = g_value_get_boolean (value);
      break;
    case PROP_EMIT_METADATA:
      filter->emit_metadata = g_value_get_boolean (value);
      break;
    default:
      G_OBJECT_WARN_INVALID_PROPERTY_ID (object, prop_id, pspec);
      break;
  }
}

static void
gst_yolo_inference_get_property (GObject * object, guint prop_id,
    GValue * value, GParamSpec * pspec)
{
  GstYoloInference *filter = GST_YOLO_INFERENCE (object);

  switch (prop_id) {
    case PROP_MODEL_PATH:
      g_value_set_string (value, filter->model_path);
      break;
    case PROP_CONFIDENCE:
      g_value_set_float (value, filter->confidence);
      break;
    case PROP_IOU_THRESHOLD:
      g_value_set_float (value, filter->iou_threshold);
      break;
    case PROP_ANNOTATE:
      g_value_set_boolean (value, filter->annotate);
      break;
    case PROP_EMIT_METADATA:
      g_value_set_boolean (value, filter->emit_metadata);
      break;
    default:
      G_OBJECT_WARN_INVALID_PROPERTY_ID (object, prop_id, pspec);
      break;
  }
}

/* Cleanup */
static void
gst_yolo_inference_finalize (GObject * object)
{
  GstYoloInference *filter = GST_YOLO_INFERENCE (object);

  g_free (filter->model_path);

  G_OBJECT_CLASS (parent_class)->finalize (object);
}

/* Start - load model */
static gboolean
gst_yolo_inference_start (GstBaseTransform * trans)
{
  GstYoloInference *filter = GST_YOLO_INFERENCE (trans);

  GST_INFO_OBJECT (filter, "Loading YOLO model: %s", filter->model_path);

  // Create YOLO runner (C++ wrapper)
  filter->yolo_runner = yolo_runner_create (filter->model_path);

  if (!filter->yolo_runner) {
    GST_ERROR_OBJECT (filter, "Failed to load YOLO model");
    return FALSE;
  }

  GST_INFO_OBJECT (filter, "YOLO model loaded successfully");
  return TRUE;
}

/* Stop - cleanup model */
static gboolean
gst_yolo_inference_stop (GstBaseTransform * trans)
{
  GstYoloInference *filter = GST_YOLO_INFERENCE (trans);

  if (filter->yolo_runner) {
    yolo_runner_destroy (filter->yolo_runner);
    filter->yolo_runner = NULL;
  }

  if (filter->frame_count > 0) {
    gdouble avg_time = filter->total_inference_time / filter->frame_count;
    GST_INFO_OBJECT (filter, "Statistics: %lu frames, avg inference: %.2f ms",
        filter->frame_count, avg_time);
  }

  return TRUE;
}

/* Transform frame in-place */
static GstFlowReturn
gst_yolo_inference_transform_ip (GstBaseTransform * trans, GstBuffer * buf)
{
  GstYoloInference *filter = GST_YOLO_INFERENCE (trans);
  GstMapInfo map;
  GstClockTime start_time, inference_time;

  if (!gst_buffer_map (buf, &map, GST_MAP_READWRITE)) {
    GST_ERROR_OBJECT (filter, "Failed to map buffer");
    return GST_FLOW_ERROR;
  }

  // Get video info from caps
  GstCaps *caps = gst_pad_get_current_caps (trans->sinkpad);
  if (!gst_video_info_from_caps (&filter->video_info, caps)) {
    GST_ERROR_OBJECT (filter, "Failed to get video info");
    gst_caps_unref (caps);
    gst_buffer_unmap (buf, &map);
    return GST_FLOW_ERROR;
  }
  gst_caps_unref (caps);

  // Run YOLO inference
  start_time = g_get_monotonic_time ();

  gboolean success = yolo_runner_infer (filter->yolo_runner,
      map.data,
      filter->video_info.width,
      filter->video_info.height,
      filter->confidence,
      filter->annotate);

  inference_time = g_get_monotonic_time () - start_time;

  if (!success) {
    GST_WARNING_OBJECT (filter, "Inference failed");
  }

  // Update statistics
  filter->frame_count++;
  filter->total_inference_time += inference_time / 1000.0;  // Convert to ms

  // Emit metadata if requested
  if (filter->emit_metadata && success) {
    // TODO: Get detection results and post as message
    GST_LOG_OBJECT (filter, "Frame %lu: inference took %.2f ms",
        filter->frame_count, inference_time / 1000.0);
  }

  gst_buffer_unmap (buf, &map);

  return GST_FLOW_OK;
}

/* Plugin entry point */
static gboolean
plugin_init (GstPlugin * plugin)
{
  return gst_element_register (plugin, "yoloinference",
      GST_RANK_NONE, GST_TYPE_YOLO_INFERENCE);
}

#ifndef PACKAGE
#define PACKAGE "yoloinference"
#endif

GST_PLUGIN_DEFINE (
    GST_VERSION_MAJOR,
    GST_VERSION_MINOR,
    yoloinference,
    "YOLO Inference Plugin",
    plugin_init,
    "1.0",
    "MIT",
    "Product Capture System",
    "https://github.com/yourrepo"
)
