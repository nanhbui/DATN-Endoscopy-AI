/**
 * GStreamer YOLO Inference Plugin
 *
 * A GStreamer element for real-time YOLO object detection and segmentation.
 */

#ifndef __GST_YOLO_INFERENCE_H__
#define __GST_YOLO_INFERENCE_H__

#include <gst/gst.h>
#include <gst/base/gstbasetransform.h>
#include <gst/video/video.h>

G_BEGIN_DECLS

#define GST_TYPE_YOLO_INFERENCE \
  (gst_yolo_inference_get_type())
#define GST_YOLO_INFERENCE(obj) \
  (G_TYPE_CHECK_INSTANCE_CAST((obj),GST_TYPE_YOLO_INFERENCE,GstYoloInference))
#define GST_YOLO_INFERENCE_CLASS(klass) \
  (G_TYPE_CHECK_CLASS_CAST((klass),GST_TYPE_YOLO_INFERENCE,GstYoloInferenceClass))
#define GST_IS_YOLO_INFERENCE(obj) \
  (G_TYPE_CHECK_INSTANCE_TYPE((obj),GST_TYPE_YOLO_INFERENCE))
#define GST_IS_YOLO_INFERENCE_CLASS(klass) \
  (G_TYPE_CHECK_CLASS_TYPE((klass),GST_TYPE_YOLO_INFERENCE))

typedef struct _GstYoloInference GstYoloInference;
typedef struct _GstYoloInferenceClass GstYoloInferenceClass;

/**
 * GstYoloInference:
 *
 * The opaque GstYoloInference data structure.
 */
struct _GstYoloInference
{
  GstBaseTransform element;

  /* Properties */
  gchar *model_path;
  gfloat confidence;
  gfloat iou_threshold;
  gboolean annotate;
  gboolean emit_metadata;

  /* Private data */
  gpointer yolo_runner;  // YoloRunner* (C++ object)

  /* Video info */
  GstVideoInfo video_info;

  /* Statistics */
  guint64 frame_count;
  gdouble total_inference_time;
};

struct _GstYoloInferenceClass
{
  GstBaseTransformClass parent_class;
};

GType gst_yolo_inference_get_type (void);

G_END_DECLS

#endif /* __GST_YOLO_INFERENCE_H__ */
