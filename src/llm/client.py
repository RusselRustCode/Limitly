import logging
from enum import Enum
from typing import Optional
from openai import OpenAI
from fastapi import HTTPException


from config.settings import settings

logger = logging.getLogger(__name__)

class LLMModel(str, Enum):
    """Все доступные модели через агрегатор rus-gpt.com"""
 
    # Anthropic Claude
    CLAUDE_HAIKU_4_5        = "anthropic/claude-haiku-4.5"
    CLAUDE_OPUS_4_5         = "anthropic/claude-opus-4.5"
    CLAUDE_OPUS_4_6         = "anthropic/claude-opus-4.6"
    CLAUDE_OPUS_4_7         = "anthropic/claude-opus-4.7"
    CLAUDE_SONNET_4_5       = "anthropic/claude-sonnet-4.5"
    CLAUDE_SONNET_4_6       = "anthropic/claude-sonnet-4.6"
 
    # DeepSeek
    DEEPSEEK_V3_2           = "deepseek/deepseek-v3.2"
    DEEPSEEK_V3_2_SPECIALE  = "deepseek/deepseek-v3.2-speciale"
 
    # Google Gemini
    GEMINI_2_5_FLASH_IMAGE  = "google/gemini-2.5-flash-image"
    GEMINI_3_FLASH_PREVIEW  = "google/gemini-3-flash-preview"
    GEMINI_3_PRO_IMAGE      = "google/gemini-3-pro-image-preview"
    GEMINI_3_PRO_PREVIEW    = "google/gemini-3-pro-preview"
    GEMINI_3_1_FLASH_IMAGE  = "google/gemini-3.1-flash-image-preview"
 
    # MiniMax
    MINIMAX_M2_1            = "minimax/minimax-m2.1"
    MINIMAX_M2_7            = "minimax/minimax-m2.7"
 
    # Moonshot
    KIMI_K2_5               = "moonshotai/kimi-k2.5"
 
    # OpenAI GPT (через агрегатор)
    GPT_OSS_120B            = "openai/gpt-oss-120b"
    GPT_OSS_20B             = "openai/gpt-oss-20b"
 
    # Qwen3
    QWEN3_30B_INSTRUCT      = "qwen/qwen3-30b-a3b-instruct-2507"
    QWEN3_30B_THINKING      = "qwen/qwen3-30b-a3b-thinking-2507"
    QWEN3_NEXT_80B_INSTRUCT = "qwen/qwen3-next-80b-a3b-instruct"
    QWEN3_NEXT_80B_THINKING = "qwen/qwen3-next-80b-a3b-thinking"
    QWEN3_VL_235B_INSTRUCT  = "qwen/qwen3-vl-235b-a22b-instruct"
    QWEN3_VL_235B_THINKING  = "qwen/qwen3-vl-235b-a22b-thinking"
    QWEN3_VL_30B_INSTRUCT   = "qwen/qwen3-vl-30b-a3b-instruct"
    QWEN3_VL_30B_THINKING   = "qwen/qwen3-vl-30b-a3b-thinking"
 
    # Qwen3.5
    QWEN3_5_122B            = "qwen/qwen3.5-122b-a10b"
    QWEN3_5_27B             = "qwen/qwen3.5-27b"
    QWEN3_5_35B             = "qwen/qwen3.5-35b-a3b"
    QWEN3_5_397B            = "qwen/qwen3.5-397b-a17b"
 
    # Z-AI GLM
    GLM_4_6V                = "z-ai/glm-4.6v"
    GLM_4_7                 = "z-ai/glm-4.7"
    GLM_4_7_FLASH           = "z-ai/glm-4.7-flash"
    GLM_5                   = "z-ai/glm-5"
    GLM_5_1                 = "z-ai/glm-5.1"
    

class ModelPreset:
    """Рекомендуемые модели под разные типы задач"""
 
    # Лучший баланс цена/качество для объяснений и тем
    DEFAULT         = LLMModel.QWEN3_NEXT_80B_INSTRUCT
 
    # Дешёвый и быстрый для тестов и задач (точность важна, контекст короткий)
    FAST_ACCURATE   = LLMModel.DEEPSEEK_V3_2
 
    # Топовый для сложных объяснений (theorist профиль)
    PREMIUM         = LLMModel.CLAUDE_SONNET_4_5
 
    # Для лёгких задач (темы, термины)
    LIGHT           = LLMModel.GLM_4_7_FLASH
    
    
class LLMClient:
    
    instance: Optional["LLMClient"] = None
    
    
    def __init__(self):
        self.client = OpenAI(
            base_url="https://rus-gpt.com/api/v1",
            api_key= settings.RUSGPT_API_KEY
        )
        
        logger.info("LLMClient (rus-gpt.com aggregator) инициализирован")
            
    
    @classmethod
    def get_instance(cls) -> "LLMClient":
        """Singletone"""
        if cls.instance is None:
            cls.instance = cls()
        return cls.instance
    
    
    def invoke(self, 
    prompt: str,
    model: LLMModel = ModelPreset.DEFAULT, 
    temperature: float = 0.7,
    max_tokens: int = 8000
    ) -> str:
        try:
            response = self.client.chat.completions.create(
                model = model.value,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            
            raw = response.choices[0].message.content
            logger.info(f"[LLMClient] model={model.value} | " f"output_len={len(raw)} chars")
            return raw
        
        except Exception as e:
            logger.error(f"[LLMClient] Ошибка вызова {model.value}: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Ошибка при обращении к LLM ({model.value}): {e}"
            )
    
llm_client = LLMClient.get_instance()
    
    
    
    