import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


class LocalQwen:
    def __init__(self, model_path):
        print(f"🚀 正在将模型加载至 1650 Ti (显存占用中...)...")
        # 针对 1650 Ti 4GB 的优化配置
        self.tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_path,
            device_map="cuda",  # 强制使用显卡
            torch_dtype="auto",  # 自动选择精度（通常是 float16）
            trust_remote_code=True
        )
        print("模型加载成功！显存已就位。")

    def chat(self, system_prompt, user_input):
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input}
        ]
        # 构造对话模板
        text = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        model_inputs = self.tokenizer([text], return_tensors="pt").to("cuda")

        # 生成答案
        generated_ids = self.model.generate(
            model_inputs.input_ids,
            max_new_tokens=512,
            temperature=0.7,
            top_p=0.9
        )

        # 剔除输入的 Prompt 部分，只保留生成的回答
        generated_ids = [
            output_ids[len(input_ids):] for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)
        ]

        return self.tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]


# 测试单例（防止多次加载撑爆显存）
# 注意：这里的路径改为你 E:\nong_wenda\qwen 的实际完整路径
MODEL_PATH = r"E:\nong_wenda\qwen"
qwen_brain = LocalQwen(MODEL_PATH)