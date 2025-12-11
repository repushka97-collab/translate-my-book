import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

MODEL_NAME = "facebook/nllb-200-distilled-1.3B"

def main():
    print("torch:", torch.__version__)

    device = "cpu"
    print("using device:", device)

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME).to(device)
    model.eval()

    text = "This is a small test sentence about rehabilitation and neurology."
    print("SRC:", text)

    # исходный язык
    tokenizer.src_lang = "eng_Latn"
    encoded = tokenizer(text, return_tensors="pt")

    # целевой язык (русский), с учётом разных версий transformers
    if hasattr(tokenizer, "lang_code_to_id"):
        bos_id = tokenizer.lang_code_to_id["rus_Cyrl"]
    else:
        bos_id = tokenizer.convert_tokens_to_ids("rus_Cyrl")

    with torch.no_grad():
        generated_tokens = model.generate(
            **encoded,
            forced_bos_token_id=bos_id,
            max_length=256,
        )

    translated = tokenizer.batch_decode(
        generated_tokens,
        skip_special_tokens=True
    )[0]

    print("TGT:", translated)

if __name__ == "__main__":
    main()
