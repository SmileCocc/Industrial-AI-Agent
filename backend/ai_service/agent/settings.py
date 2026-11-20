from pydantic import Field, SecretStr, ValidationError

from common.config import Settings


class AgentError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


class AgentSettings(Settings):
    model_provider: str = 'openai_compatible'
    model_base_url: str = ''
    model_name: str = ''
    model_api_key: SecretStr = SecretStr('')
    model_temperature: float = Field(0.2, ge=0, le=2)
    model_max_tokens: int = Field(4096, gt=0)
    model_timeout: float = Field(60, gt=0, allow_inf_nan=False)
    agent_timeout: float = Field(120, gt=0, allow_inf_nan=False)
    agent_max_steps: int = Field(8, gt=0)
    agent_max_tool_calls: int = Field(15, gt=0)


def get_agent_settings() -> AgentSettings:
    try:
        return AgentSettings()
    except ValidationError:
        raise AgentError(503, 'Agent 配置无效') from None
