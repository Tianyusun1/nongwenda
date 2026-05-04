import os
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

class LocalQwen:
    def __init__(self, model_path):
        self.tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_path,
            device_map='cuda' if torch.cuda.is_available() else 'cpu',
            torch_dtype='auto',
            trust_remote_code=True
        )

    def chat(self, system_prompt, user_input):
        messages = [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_input},
        ]
        text = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        model_inputs = self.tokenizer([text], return_tensors='pt').to(self.model.device)
        generated_ids = self.model.generate(model_inputs.input_ids, max_new_tokens=512, temperature=0.5, top_p=0.9)
        generated_ids = [output_ids[len(input_ids):] for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)]
        return self.tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]

MODEL_PATH = os.getenv('QWEN_MODEL_PATH', r'E:\nong_wenda\qwen')
qwen_brain = LocalQwen(MODEL_PATH)
