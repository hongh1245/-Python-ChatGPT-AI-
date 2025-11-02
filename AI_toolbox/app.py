import os
import io
import requests
from typing import Optional
from PIL import Image
import streamlit as st
from streamlit_option_menu import option_menu

# =========================
# 基本設定
# =========================
st.set_page_config(page_title="AI 百寶箱（Gemini + Stability）", page_icon="🤖", layout="wide")

# 讀取環境變數（Gemini 兼容 GOOGLE_API_KEY / GEMINI_API_KEY）
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or ""
STABILITY_API_KEY = os.getenv("STABILITY_API_KEY", "")

# 側邊欄：功能選單 + 狀態燈
with st.sidebar:
    choice = option_menu(
        "AI 實用百寶箱",
        ["🏠 簡介", "💬 聊天（Gemini）", "🎨 生圖（Stability）"],
        icons=["house", "chat-dots", "palette"],
        menu_icon="robot",
        default_index=0
    )
    st.markdown("---")
    st.caption("🔑 金鑰狀態")
    st.write(f"Gemini Key：{'🟢 已設定' if GOOGLE_API_KEY else '🔴 未讀到（請設 GOOGLE_API_KEY 或 GEMINI_API_KEY）'}")
    st.write(f"Stability Key：{'🟢 已設定' if STABILITY_API_KEY else '🔴 未讀到（請設 STABILITY_API_KEY）'}")
    st.markdown("---")
    st.caption("📝 小提示：請在 **新開的終端機** 中執行以讀到最新環境變數。")

# =========================
# Gemini 工具：自動選模型 + 產生回覆
# =========================
def _pick_gemini_model(api_key: str, prefer_list=None) -> str:
    """從 prefer_list 依序嘗試；若建立失敗，動態從 list_models() 找支援 generateContent 的第一個。"""
    import google.generativeai as genai
    genai.configure(api_key=api_key)

    # 首選清單（可自行調整順序）
    prefer_list = prefer_list or [
        "models/gemini-1.5-flash",
        "models/gemini-1.5-flash-8b",
        "models/gemini-1.5-pro",
    ]

    # 嘗試首選名單是不是能直接初始化
    for name in prefer_list:
        try:
            _ = genai.GenerativeModel(name)  # 不呼叫 API，只測能否構建
            return name
        except Exception:
            continue

    # 若都不行，動態列出可用模型作 fallback
    try:
        for m in genai.list_models():
            methods = getattr(m, "supported_generation_methods", [])
            if "generateContent" in methods:
                # 優先挑含 "gemini-1.5" 的
                if "gemini-1.5" in m.name:
                    return m.name
        # 再挑任一支援 generateContent 的
        for m in genai.list_models():
            methods = getattr(m, "supported_generation_methods", [])
            if "generateContent" in methods:
                return m.name
    except Exception:
        pass

    # 都找不到就拋錯
    raise RuntimeError("此 API 金鑰查無可用 Gemini 模型，請至 AI Studio 檢查權限或更換金鑰。")

def gemini_chat(prompt: str, model_name: Optional[str] = None) -> str:
    """送文字給 Gemini，回傳文字答案。自動偵測可用模型。"""
    if not GOOGLE_API_KEY:
        raise RuntimeError("找不到 GOOGLE_API_KEY / GEMINI_API_KEY，請先設定環境變數。")
    import google.generativeai as genai
    genai.configure(api_key=GOOGLE_API_KEY)

    # 若未指定，動態選一個
    use_model = model_name or _pick_gemini_model(GOOGLE_API_KEY)
    model = genai.GenerativeModel(use_model)
    resp = model.generate_content(prompt)
    text = getattr(resp, "text", "") or ""
    return text.strip()

# =========================
# Stability 工具：文字生圖（Core 端點）
# =========================
def stability_generate_image(prompt: str, size: str = "512x512") -> Image.Image:
    if not STABILITY_API_KEY:
        raise RuntimeError("找不到 STABILITY_API_KEY，請先設定環境變數。")

    url = "https://api.stability.ai/v2beta/stable-image/generate/core"
    width, height = [int(x) for x in size.split("x")]

    headers = {
        "Authorization": f"Bearer {STABILITY_API_KEY}"
    }
    files = {
        "prompt": (None, prompt),
        "mode": (None, "text-to-image"),
        "output_format": (None, "png"),
        "width": (None, str(width)),
        "height": (None, str(height)),
    }

    r = requests.post(url, headers=headers, files=files, timeout=120)
    if r.status_code == 200:
        return Image.open(io.BytesIO(r.content))
    else:
        raise RuntimeError(f"Stability API 失敗：{r.status_code} {r.text}")

# =========================
# 頁面：簡介
# =========================
if choice == "🏠 簡介":
    st.title("🤖 AI 實用百寶箱")
    st.write("""
    - **聊天**：Google *Gemini*（免費額度適合作業/報告）。  
    - **生圖**：*Stability*（文字轉圖片）。  
    - **金鑰**請用環境變數：`GOOGLE_API_KEY`（或 `GEMINI_API_KEY`）、`STABILITY_API_KEY`。  
    """)
    with st.expander("如何設定環境變數（PowerShell）", expanded=False):
        st.code(
            'setx GOOGLE_API_KEY "你的_Gemini_API_Key"\n'
            'setx STABILITY_API_KEY "你的_Stability_API_Key"\n'
            "# 關閉後重開 PowerShell / VS Code，再執行：\n"
            'python -m streamlit run app.py',
            language="powershell"
        )

# =========================
# 頁面：Gemini 聊天
# =========================
elif choice == "💬 聊天（Gemini）":
    st.title("💬 Gemini 對話室")
    st.caption("預設自動選擇可用模型（優先：models/gemini-1.5-flash）。")
    user_input = st.text_area("輸入訊息：", placeholder="例如：請用三點條列說明量子糾纏")

    # 可選：手動指定模型（進階）
    with st.expander("進階：手動指定模型名稱（可留空）", expanded=False):
        manual_model = st.text_input("模型名稱（例如：models/gemini-1.5-flash）", value="")

    if st.button("送出"):
        if not user_input.strip():
            st.warning("請先輸入訊息")
        else:
            with st.spinner("Gemini 回覆中..."):
                try:
                    model_override = manual_model.strip() or None
                    answer = gemini_chat(user_input, model_name=model_override)
                    if answer:
                        st.success(answer)
                    else:
                        st.warning("沒有取得回覆文字，請稍後再試")
                except Exception as e:
                    st.error(f"發生錯誤：{e}")

# =========================
# 頁面：Stability 生圖
# =========================
elif choice == "🎨 生圖（Stability）":
    st.title("🎨 文生圖（Stability）")
    col1, col2 = st.columns([2, 1])
    with col1:
        prompt = st.text_area("輸入繪圖描述：", placeholder="例如：一隻戴著太空頭盔的黑貓，像素風")
    with col2:
        size = st.selectbox("尺寸", ["512x512", "768x512", "512x768", "1024x1024"], index=0)

    if st.button("生成圖片"):
        if not prompt.strip():
            st.warning("請先輸入描述")
        else:
            with st.spinner("Stability 生成中..."):
                try:
                    img = stability_generate_image(prompt, size=size)
                    st.image(img, caption="Stability 生成結果", use_container_width=True)
                    # 下載按鈕
                    buf = io.BytesIO()
                    img.save(buf, format="PNG")
                    st.download_button("下載圖片（PNG）", data=buf.getvalue(),
                                       file_name="stability.png", mime="image/png")
                except Exception as e:
                    st.error(f"發生錯誤：{e}")
