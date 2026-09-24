
"""
Multi-Provider Failover Router for Basalt AI Studio.
Ensures high availability by routing requests through Groq, OpenRouter, and NVIDIA.
"""
import os
import requests
from typing import Any, Dict, Optional, List

class FreeLLMRouter:
    def __init__(self):
        # Configuration for free-tier models across providers
        self.providers = [
            {
                "name": "groq",
                "base_url": "https://api.groq.com/openai/v1",
                "api_key": os.getenv("GROQ_API_KEY"),
                "model": "llama3-70b-8192",
                "priority": 1
            },
            {
                "name": "openrouter",
                "base_url": "https://openrouter.ai/api/v1",
                "api_key": os.getenv("OPENROUTER_API_KEY"),
                "model": "meta-llama/llama-3-8b-instruct:free",
                "priority": 2
            },
            {
                "name": "nvidia",
                "base_url": "https://integrate.api.nvidia.com/v1",
                "api_key": os.getenv("NVIDIA_API_KEY"),
                "model": "meta/llama-3.1-8b-instruct",
                "priority": 3
            }
        ]

    def call_chat(self, prompt: str, system_prompt: str = "You are a helpful assistant.") -> Optional[str]:
        for provider in self.providers:
            if not provider["api_key"]:
                continue
            
            try:
                response = requests.post(
                    f"{provider['base_url']}/chat/completions",
                    headers={"Authorization": f"Bearer {provider['api_key']}"},
                    json={
                        "model": provider["model"],
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.0
                    },
                    timeout=10
                )
                if response.status_code == 200:
                    return response.json()['choices'][0]['message']['content'].strip()
                
                print(f"Provider {provider['name']} failed with status {response.status_code}. Falling back...")
            except Exception as e:
                print(f"Provider {provider['name']} encountered error: {e}. Falling back...")
        
        return None

    def call_embedding(self, text: str) -> Optional[List[float]]:
        # Embeddings are handled slightly differently across providers.
        # NVIDIA NIM is the most stable for free embeddings.
        providers_emb = [
            {
                "name": "nvidia",
                "base_url": "https://integrate.api.nvidia.com/v1",
                "api_key": os.getenv("NVIDIA_API_KEY"),
                "model": "nvidia/nv-embedqa-e5-v5"
            },
            {
                "name": "openrouter",
                "base_url": "https://openrouter.ai/api/v1",
                "api_key": os.getenv("OPENROUTER_API_KEY"),
                "model": "openai/text-embedding-3-small" 
            }
        ]

        for provider in providers_emb:
            if not provider["api_key"]:
                continue
            try:
                response = requests.post(
                    f"{provider['base_url']}/embeddings",
                    headers={"Authorization": f"Bearer {provider['api_key']}"},
                    json={"input": text, "model": provider["model"]},
                    timeout=10
                )
                if response.status_code == 200:
                    return response.json()['data'][0]['embedding']
            except Exception as e:
                print(f"Embedding provider {provider['name']} failed: {e}")
        
        return None
