import qrcode
import os
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

def create_slots_qr(count=36):
    """
    지정된 개수만큼 텍스트가 포함된 QR 코드를 생성하고,
    개별 이미지 및 A4 사이즈 PDF 파일(18개씩)로 저장합니다.
    """
    now = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_parent_dir = os.path.join(base_dir, "qr_outputs")
    target_dir = os.path.join(output_parent_dir, now)

    os.makedirs(target_dir, exist_ok=True)
    print(f"Target Directory: {target_dir}")

    try:
        font = ImageFont.truetype("malgun.ttf", 45) 
    except IOError:
        try:
            font = ImageFont.truetype("arial.ttf", 45)
        except IOError:
            font = ImageFont.load_default()

    qr_images = []

    for i in range(1, count + 1):
        qr_data = f"SLOT_{i:02d}"
        display_text = f"SLOT-{i:02d}"

        qr = qrcode.QRCode(box_size=12, border=2)
        qr.add_data(qr_data)
        qr.make(fit=True)
        img_qr = qr.make_image(fill_color="black", back_color="white").convert('RGB')

        w, h = img_qr.size
        text_padding = 80
        img_with_text = Image.new('RGB', (w, h + text_padding), 'white')
        img_with_text.paste(img_qr, (0, 0))

        draw = ImageDraw.Draw(img_with_text)
        bbox = draw.textbbox((0, 0), display_text, font=font)
        text_w = bbox[2] - bbox[0]
        text_x = (w - text_w) / 2
        text_y = h + 10 
        
        draw.text((text_x, text_y), display_text, fill="black", font=font)

        file_path = os.path.join(target_dir, f"{qr_data}.png")
        img_with_text.save(file_path)
        
        qr_images.append(img_with_text)

    # --- 여기서부터 수정됨 (크기 빵빵하게 키우기) ---
    def make_pdf(image_list, pdf_filename):
        a4_w, a4_h = 2480, 3508 
        canvas = Image.new('RGB', (a4_w, a4_h), 'white')
        
        # [수정 1] 종이 테두리 여백을 150에서 80으로 확 줄임 (공간 확보)
        margin_x, margin_y = 80, 80
        cell_w = (a4_w - 2 * margin_x) // 3
        cell_h = (a4_h - 2 * margin_y) // 6

        for idx, img in enumerate(image_list):
            row = idx // 3
            col = idx % 3
            
            # [수정 2] 셀 안에서 차지하는 비율을 80% -> 95%로 대폭 확대
            max_img_w = int(cell_w * 0.95)
            max_img_h = int(cell_h * 0.95)
            img_copy = img.copy()
            img_copy.thumbnail((max_img_w, max_img_h), Image.Resampling.LANCZOS)

            x = margin_x + col * cell_w + (cell_w - img_copy.width) // 2
            y = margin_y + row * cell_h + (cell_h - img_copy.height) // 2
            
            canvas.paste(img_copy, (x, y))

        pdf_path = os.path.join(target_dir, pdf_filename)
        canvas.save(pdf_path, "PDF", resolution=300.0)
        print(f"✅ PDF 저장 완료: {pdf_path}")

    if len(qr_images) >= 18:
        make_pdf(qr_images[:18], "slots_01_to_18.pdf")
    else:
        make_pdf(qr_images, "slots_01_to_18.pdf")

    if len(qr_images) > 18:
        make_pdf(qr_images[18:36], "slots_19_to_36.pdf")

    os.startfile(target_dir)

if __name__ == "__main__":
    create_slots_qr()