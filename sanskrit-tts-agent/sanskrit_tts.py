import torch
import soundfile as sf

from parler_tts import ParlerTTSForConditionalGeneration
from transformers import AutoTokenizer

MODEL = "ai4bharat/indic-parler-tts"

device = "cuda:0" if torch.cuda.is_available() else "cpu"

print("Loading model...")

model = ParlerTTSForConditionalGeneration.from_pretrained(
    MODEL
).to(device)

tokenizer = AutoTokenizer.from_pretrained(MODEL)

description_tokenizer = AutoTokenizer.from_pretrained(
    model.config.text_encoder._name_or_path
)

text = """
प्रणम्य शिरसा देवं गौरीपुत्रं विनायकम् ।
भक्तावासं स्मरेन्नित्यमायुःकामार्थसिद्धये ॥
"""

description = """
Aryan speaks Sanskrit in a clear, calm and reverent male voice.
The pronunciation is precise and natural.
The delivery is slow and suitable for Sanskrit devotional chanting.
There are gentle pauses between verses.
The recording has very clear audio with no background noise.
"""

description_inputs = description_tokenizer(
    description,
    return_tensors="pt"
).to(device)

text_inputs = tokenizer(
    text,
    return_tensors="pt"
).to(device)

generation = model.generate(
    input_ids=description_inputs.input_ids,
    attention_mask=description_inputs.attention_mask,
    prompt_input_ids=text_inputs.input_ids,
    prompt_attention_mask=text_inputs.attention_mask,
)

audio = generation.cpu().numpy().squeeze()

sf.write(
    "sanskrit_output.mp3",
    audio,
    model.config.sampling_rate
)

print("Saved: sanskrit_output.mp3")