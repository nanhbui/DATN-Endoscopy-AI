"""
Generate VQA instruction pairs từ HyperKvasir cho LLaVA-Med fine-tuning.

Output: data/llava_finetune/train.json (ShareGPT format)

Mỗi ảnh sinh ra 2-3 QA pairs:
  1. Nhận dạng tổn thương / cấu trúc
  2. Đánh giá mức độ / ý nghĩa lâm sàng
  3. Khuyến nghị hành động (chỉ với lesion)
"""

import json
import random
from pathlib import Path

# ─── Cấu hình ────────────────────────────────────────────────────────────────

IMAGE_DIR  = Path("data/hyperkvasir_yolo/images/train")
OUTPUT_DIR = Path("data/llava_finetune")
OUTPUT_FILE = OUTPUT_DIR / "train.json"
RANDOM_SEED = 42

# ─── Template QA theo class ──────────────────────────────────────────────────

QA_TEMPLATES: dict[str, list[dict]] = {

    "pylorus": [
        {
            "q": "Hình ảnh nội soi này cho thấy cấu trúc gì?",
            "a": "Hình ảnh cho thấy môn vị (pylorus) — van cơ nằm giữa dạ dày và tá tràng. Cấu trúc hình tròn, niêm mạc xung quanh bình thường, không có dấu hiệu bất thường.",
        },
        {
            "q": "Niêm mạc vùng môn vị có bất thường không?",
            "a": "Niêm mạc vùng môn vị trông bình thường. Không quan sát thấy loét, sung huyết, hay tổn thương nào đáng lo ngại. Đây là hình ảnh môn vị bình thường.",
        },
    ],

    "retroflex-stomach": [
        {
            "q": "Đây là góc chụp nội soi nào của dạ dày?",
            "a": "Đây là hình ảnh dạ dày chụp theo góc nhìn ngược (retroflex view) — ống soi uốn cong nhìn lại về phía tâm vị. Góc này cho phép quan sát vùng đáy vị và tâm vị mà không thể thấy ở góc thẳng.",
        },
        {
            "q": "Vùng tâm vị trong ảnh có dấu hiệu bất thường không?",
            "a": "Vùng tâm vị nhìn từ góc retroflex có niêm mạc bình thường, không có khối u, loét hay sung huyết. Đây là hình ảnh dạ dày bình thường.",
        },
    ],

    "z-line": [
        {
            "q": "Đường Z-line trong hình ảnh nội soi này là gì?",
            "a": "Z-line (còn gọi là đường ora serrata hay squamocolumnar junction) là ranh giới giữa biểu mô vảy của thực quản và biểu mô trụ của dạ dày. Trong ảnh, đường Z-line hiện rõ và đều đặn — đây là hình ảnh bình thường.",
        },
        {
            "q": "Ranh giới thực quản-dạ dày trong ảnh có bất thường không?",
            "a": "Ranh giới Z-line trông bình thường, đường phân giới rõ ràng và đều. Không có dấu hiệu của niêm mạc Barrett hay viêm thực quản.",
        },
    ],

    "barretts": [
        {
            "q": "Hình ảnh nội soi này cho thấy tình trạng gì?",
            "a": "Hình ảnh cho thấy thực quản Barrett (Barrett's esophagus) — tình trạng niêm mạc thực quản bị thay thế bằng biểu mô trụ dạng ruột. Đặc trưng bởi vùng niêm mạc màu hồng cam bất thường kéo dài trên đường Z-line.",
        },
        {
            "q": "Mức độ nguy hiểm của tổn thương này là gì và cần làm gì tiếp theo?",
            "a": "Thực quản Barrett là tình trạng tiền ung thư. Niêm mạc dị sản có nguy cơ tiến triển thành ung thư biểu mô tuyến thực quản. Cần sinh thiết để đánh giá mức độ loạn sản (dysplasia). Nếu có loạn sản độ cao, cần can thiệp nội soi (RFA, EMR) hoặc phẫu thuật.",
        },
        {
            "q": "Đặc điểm hình ảnh nào giúp chẩn đoán Barrett's esophagus?",
            "a": "Các đặc điểm chính: (1) Vùng niêm mạc màu hồng-cam kéo dài trên đường Z-line ≥1cm; (2) Bề mặt có cấu trúc nhung mao (villous pattern); (3) Mạch máu bề mặt bất thường. Cần NBI hoặc nhuộm acetic acid để đánh giá chi tiết hơn.",
        },
    ],

    "barretts-short-segment": [
        {
            "q": "Hình ảnh này cho thấy dạng Barrett nào?",
            "a": "Đây là Barrett thực quản đoạn ngắn (short-segment Barrett's) — niêm mạc dị sản dài dưới 3cm trên đường Z-line. Ít phổ biến hơn Barrett dài đoạn nhưng vẫn có nguy cơ tiến triển ung thư.",
        },
        {
            "q": "Cần theo dõi tổn thương này như thế nào?",
            "a": "Barrett đoạn ngắn không loạn sản cần nội soi kiểm tra định kỳ 3-5 năm/lần. Cần sinh thiết theo giao thức Seattle (4 góc mỗi 2cm). Kiểm soát trào ngược dạ dày-thực quản bằng PPI để ngăn tiến triển.",
        },
    ],

    "esophagitis-a": [
        {
            "q": "Hình ảnh nội soi thực quản này cho thấy tình trạng gì?",
            "a": "Hình ảnh cho thấy viêm thực quản trào ngược độ A theo phân loại Los Angeles — có các vết ăn mòn (erosion) dài dưới 5mm, giới hạn trên đỉnh các nếp niêm mạc, không hợp lưu.",
        },
        {
            "q": "Viêm thực quản độ A có cần điều trị tích cực không?",
            "a": "Viêm thực quản độ A là mức độ nhẹ. Điều trị bằng PPI (omeprazole, esomeprazole) 4-8 tuần thường hiệu quả. Kết hợp thay đổi lối sống: tránh nằm ngay sau ăn, giảm cân nếu thừa cân, tránh thức ăn kích thích acid.",
        },
    ],

    "esophagitis-b-d": [
        {
            "q": "Mức độ viêm thực quản trong hình ảnh này là bao nhiêu?",
            "a": "Hình ảnh cho thấy viêm thực quản trào ngược độ B-D theo phân loại Los Angeles — các vết ăn mòn dài trên 5mm, có thể hợp lưu (độ C) hoặc lan rộng trên 75% chu vi thực quản (độ D). Đây là mức độ trung bình đến nặng.",
        },
        {
            "q": "Cần xử trí như thế nào với viêm thực quản độ B-D?",
            "a": "Cần điều trị tích cực: PPI liều cao 2 lần/ngày trong 8 tuần, sau đó duy trì PPI liều thấp lâu dài. Nội soi kiểm tra sau 8 tuần để đánh giá lành thương. Nếu không đáp ứng, cần xem xét phẫu thuật chống trào ngược (Nissen fundoplication).",
        },
        {
            "q": "Biến chứng nào có thể xảy ra nếu không điều trị?",
            "a": "Viêm thực quản nặng không điều trị có thể dẫn đến: hẹp thực quản do sẹo xơ, Barrett thực quản (tiền ung thư), ung thư biểu mô tuyến thực quản, chảy máu tiêu hóa. Cần điều trị và theo dõi tích cực.",
        },
    ],

    "polyps": [
        {
            "q": "Hình ảnh nội soi cho thấy tổn thương gì?",
            "a": "Hình ảnh cho thấy một polyp niêm mạc — tổn thương lồi vào trong lòng ống tiêu hóa. Cần đánh giá hình dạng (cuống/không cuống), kích thước, và đặc điểm bề mặt để xác định nguy cơ.",
        },
        {
            "q": "Polyp này có nguy cơ ung thư không và cần làm gì?",
            "a": "Mọi polyp đều cần được cắt bỏ và gửi giải phẫu bệnh. Polyp tuyến (adenoma) có nguy cơ ung thư hóa, đặc biệt khi: kích thước >1cm, có thành phần nhung mao, loạn sản độ cao. Cần cắt polyp nội soi (polypectomy hoặc EMR) ngay trong lần nội soi.",
        },
        {
            "q": "Đặc điểm nào trong hình ảnh gợi ý polyp lành tính hay ác tính?",
            "a": "Gợi ý lành tính: bề mặt trơn láng, có cuống rõ, kích thước nhỏ (<1cm), màu sắc đồng đều. Gợi ý ác tính: bề mặt sần sùi không đều, loét, cứng khi chạm, kích thước lớn, mất cấu trúc pit pattern. Cần NBI/ChromoEndoscopy để đánh giá chi tiết.",
        },
    ],
}


# ─── Hàm tạo conversation ────────────────────────────────────────────────────

def make_conversation(image_path: str, class_name: str) -> dict | None:
    templates = QA_TEMPLATES.get(class_name)
    if not templates:
        return None

    # Chọn ngẫu nhiên 1-2 QA pairs
    selected = random.sample(templates, k=min(2, len(templates)))

    conversations = []
    for i, qa in enumerate(selected):
        # Turn 1: human hỏi (chỉ turn đầu có ảnh)
        human_msg = qa["q"]
        if i == 0:
            human_msg = f"<image>\n{human_msg}"
        conversations.append({"from": "human", "value": human_msg})
        conversations.append({"from": "gpt", "value": qa["a"]})

    return {
        "id": Path(image_path).stem,
        "image": image_path,
        "conversations": conversations,
    }


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    random.seed(RANDOM_SEED)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    images = sorted(IMAGE_DIR.glob("*.jpg")) + sorted(IMAGE_DIR.glob("*.png"))
    print(f"Tìm thấy {len(images)} ảnh trong {IMAGE_DIR}")

    records = []
    skipped = 0

    for img_path in images:
        # Extract class name từ prefix của filename
        class_name = img_path.stem.split("_")[0]
        # Xử lý class có dấu gạch ngang trong tên (vd: barretts-short-segment)
        # Thử match từ dài nhất trước
        matched_class = None
        for cls in sorted(QA_TEMPLATES.keys(), key=len, reverse=True):
            if img_path.stem.startswith(cls.replace("-", "-")):
                matched_class = cls
                break

        record = make_conversation(str(img_path.resolve()), matched_class or class_name)
        if record:
            records.append(record)
        else:
            skipped += 1

    print(f"Generated: {len(records)} samples  |  Skipped: {skipped}")

    # Thống kê theo class
    from collections import Counter
    class_counts = Counter()
    for r in records:
        cls = "_".join(r["id"].split("_")[:-1]) if "_" in r["id"] else r["id"]
        # Lấy class từ image path
        img_stem = Path(r["image"]).stem
        for cls_name in sorted(QA_TEMPLATES.keys(), key=len, reverse=True):
            if img_stem.startswith(cls_name):
                class_counts[cls_name] += 1
                break

    for cls, cnt in sorted(class_counts.items()):
        print(f"  {cnt:5d}  {cls}")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    print(f"\nLưu vào: {OUTPUT_FILE}  ({OUTPUT_FILE.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()