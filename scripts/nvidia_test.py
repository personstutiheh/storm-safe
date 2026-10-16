import os
from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()
client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1", api_key=os.getenv("NVIDIA_API_KEY") )
models = [m.id for m in client.models.list().data]
print([m for m in models if "nemotron" in m.lower()])