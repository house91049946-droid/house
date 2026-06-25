"""食物熱量估算 App (Gradio + Google Gemini)

使用者上傳一張圖片：
- 如果是食物 -> 估算大概的熱量並說明
- 如果不是食物 -> 回應「這不是食物」

模型：Google Gemini（多模態視覺）
API Key：透過環境變數 GOOGLE_API_KEY 提供（在 Hugging Face Space 用 Secrets 設定）。
"""

import os

import gradio as gr
from google import genai
from google.genai import types
from PIL import Image
from pydantic import BaseModel

# 可用環境變數覆寫模型名稱，預設使用支援視覺且快速的 flash 模型
MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")


class FoodAnalysis(BaseModel):
    """模型回傳的結構化結果。"""

    is_food: bool          # 圖片中是否為食物 / 飲料
    food_name: str         # 食物名稱（若非食物則留空字串）
    estimated_calories: int  # 估算總熱量 (kcal)，非食物為 0
    portion_note: str      # 份量假設說明（例如「假設一份約 300g」）
    explanation: str       # 簡短說明 / 熱量組成


PROMPT = (
    "你是一位專業的營養師。請仔細觀察這張圖片並判斷：\n"
    "1. 圖片裡的主體是否為『可食用的食物或飲料』。\n"
    "2. 如果是食物：請辨識食物名稱，並根據常見份量估算『總熱量 (kcal)』，"
    "在 portion_note 說明你假設的份量，在 explanation 簡短說明熱量主要來源。\n"
    "3. 如果不是食物（例如人、風景、物品、文件等）：is_food 設為 false，"
    "estimated_calories 設為 0，其他文字欄位留空或簡短說明看到的內容。\n"
    "所有文字請使用『繁體中文』回答。"
)


def _get_client() -> genai.Client:
    """建立 Gemini client，若沒有 API Key 則拋出友善錯誤。"""
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise gr.Error(
            "尚未設定 GOOGLE_API_KEY。請在 Hugging Face Space 的 "
            "Settings → Variables and secrets 新增 Secret『GOOGLE_API_KEY』，"
            "本機測試則請設定環境變數。"
        )
    return genai.Client(api_key=api_key)


def analyze_image(image: Image.Image) -> str:
    """分析圖片並回傳 Markdown 結果。"""
    if image is None:
        return "⚠️ 請先上傳一張圖片。"

    client = _get_client()

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[PROMPT, image],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=FoodAnalysis,
                temperature=0.2,
            ),
        )
    except Exception as exc:  # noqa: BLE001 - 對使用者顯示友善訊息
        raise gr.Error(f"呼叫 Google Gemini 失敗：{exc}")

    result: FoodAnalysis = response.parsed

    if result is None:
        return "❌ 無法解析模型回應，請再試一次。"

    if not result.is_food:
        return "🚫 **這不是食物。**\n\n請上傳一張食物或飲料的照片再試試看。"

    name = result.food_name or "未知食物"
    return (
        f"🍽️ **食物**：{name}\n\n"
        f"🔥 **估算熱量**：約 **{result.estimated_calories} kcal**\n\n"
        f"⚖️ **份量假設**：{result.portion_note}\n\n"
        f"📝 **說明**：{result.explanation}\n\n"
        f"---\n"
        f"_※ 熱量為 AI 依照片估算，僅供參考，實際數值依食材與份量而異。_"
    )


with gr.Blocks(title="食物熱量估算器") as demo:
    gr.Markdown(
        "# 🍔 食物熱量估算器\n"
        "上傳一張**食物**照片，AI 會估算大概的熱量。\n"
        "如果照片裡不是食物，會告訴你「這不是食物」。"
    )
    with gr.Row():
        with gr.Column():
            image_input = gr.Image(type="pil", label="上傳食物照片")
            analyze_btn = gr.Button("分析熱量", variant="primary")
        with gr.Column():
            output = gr.Markdown(label="分析結果")

    analyze_btn.click(fn=analyze_image, inputs=image_input, outputs=output)
    image_input.upload(fn=analyze_image, inputs=image_input, outputs=output)


if __name__ == "__main__":
    demo.launch(theme=gr.themes.Soft())
