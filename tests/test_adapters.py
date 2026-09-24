import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from agentinspector.models import AgentConfig, AgentFramework, ExecutionTrace, ToolCall
from agentinspector.adapters.integrations import LangChainAdapter, OpenAIAssistantAdapter, CrewAIAdapter, get_adapter
from agentinspector.adapters.langchain_handler import TraceCallbackHandler

# --- Fixtures ---

@pytest.fixture
def mock_config():
    return AgentConfig(
        agent_id="test-agent",
        name="Test Agent",
        framework=AgentFramework.LANGCHAIN,
        metadata={"assistant_id": "asst_123"}
    )

@pytest.fixture
def mock_langchain_agent():
    agent = AsyncMock()
    # Simulate a standard LangChain response
    agent.ainvoke.return_value = "The capital of France is Paris."
    return agent

@pytest.fixture
def mock_openai_client():
    client = MagicMock()
    # Mock Thread
    client.beta.threads.create.return_value = MagicMock(id="thread_123")
    client.beta.threads.messages.create.return_value = MagicMock()
    
    # Mock Run
    client.beta.threads.runs.create.return_value = MagicMock(id="run_123")
    
    # Mock Run Status (simulate progression: in_progress -> completed)
    status_mock = MagicMock()
    status_mock.status = "completed"
    client.beta.threads.runs.retrieve.return_value = status_mock
    
    # Mock Run Steps (Deep Tracing)
    mock_step = MagicMock()
    mock_step.step_details.type = "tool_calls"
    mock_tool_call = MagicMock()
    mock_tool_call.function.name = "get_weather"
    mock_tool_call.function.arguments = '{"location": "London"}'
    mock_step.step_details.tool_calls = [mock_tool_call]
    
    client.beta.threads.runs.steps.list.return_value = MagicMock(data=[mock_step])
    
    # Mock Final Message
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=MagicMock(value="The weather is sunny."))]
    client.beta.threads.messages.list.return_value = MagicMock(data=[mock_msg])
    
    return client

# --- TraceCallbackHandler Tests ---

def test_callback_handler_latency_capture():
    handler = TraceCallbackHandler()
    
    # Simulate tool start/end
    handler.on_tool_start({"name": "test_tool"}, "input_val")
    import time
    time.sleep(0.01) # simulate work
    handler.on_tool_end("output_val")
    
    trace = handler.get_trace()
    assert len(trace.tool_calls) == 1
    assert trace.tool_calls[0].name == "test_tool"
    assert trace.tool_calls[0].result == "output_val"
    assert trace.tool_calls[0].latency_ms > 0

# --- LangChainAdapter Tests ---

@pytest.mark.asyncio
async def test_langchain_adapter_success(mock_langchain_agent, mock_config):
    adapter = LangChainAdapter(mock_langchain_agent, mock_config)
    trace = await adapter.run("Hello")
    
    assert isinstance(trace, ExecutionTrace)
    assert trace.response == "The capital of France is Paris."
    assert trace.framework == "langchain"
    mock_langchain_agent.ainvoke.assert_called_once()

# --- OpenAIAssistantAdapter Tests ---

@pytest.mark.asyncio
async def test_openai_adapter_deep_trace(mock_openai_client, mock_config):
    adapter = OpenAIAssistantAdapter(mock_openai_client, mock_config)
    trace = await adapter.run("What's the weather?")
    
    assert trace.response == "The weather is sunny."
    assert len(trace.tool_calls) == 1
    assert trace.tool_calls[0]["name"] == "get_weather"
    assert "London" in trace.tool_calls[0]["arguments"]
    assert trace.framework == AgentFramework.OPENAI

@pytest.mark.asyncio
async def test_openai_adapter_failure(mock_openai_client, mock_config):
    # Force run to fail
    status_mock = MagicMock()
    status_mock.status = "failed"
    mock_openai_client.beta.threads.runs.retrieve.return_value = status_mock
    
    adapter = OpenAIAssistantAdapter(mock_openai_client, mock_config)
    with pytest.raises(RuntimeError, match="OpenAI Assistant run failed"):
        await adapter.run("Fail me")

# --- CrewAIAdapter Tests ---

@pytest.mark.asyncio
async def test_crewai_adapter_execution(mock_config):
    mock_crew = MagicMock()
    mock_crew.agents = [MagicMock()]
    mock_crew.agents[0].llm = MagicMock()
    mock_crew.kickoff.return_value = "CrewAI Result"
    
    adapter = CrewAIAdapter(mock_crew, mock_config)
    trace = await adapter.run("Task")
    
    assert trace.response == "CrewAI Result"
    assert trace.framework == "crewai"

# --- Factory Tests ---

def test_get_adapter_factory(mock_config):
    # Test LangChain
    mock_config.framework = AgentFramework.LANGCHAIN
    adapter = get_adapter(MagicMock(), mock_config)
    assert isinstance(adapter, LangChainAdapter)
    
    # Test OpenAI
    mock_config.framework = AgentFramework.OPENAI
    adapter = get_adapter(MagicMock(), mock_config)
    assert isinstance(adapter, OpenAIAssistantAdapter)
    
    # Test Unsupported
    mock_config.framework = "non_existent_framework"
    with pytest.raises(NotImplementedError):
        get_adapter(MagicMock(), mock_config)
