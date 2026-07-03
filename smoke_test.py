from src import ComfreyConfig, ComfreyFramework
from src.embedding_provider import EmbeddingProvider
from src.openai_compatible_client import OpenAICompatibleClient


def main():
    config = ComfreyConfig.create_lightweight_config()
    comfrey = ComfreyFramework(config)

    @comfrey
    def repeated_task_list(prompt):
        return "Plan dinner. Plan dinner. Write notes."

    first = repeated_task_list("prepare farewell tasks")
    second = repeated_task_list("prepare farewell tasks")

    assert first == "Plan dinner. Write notes."
    assert second == first
    assert repeated_task_list.__comfrey_instrumentation__["instruction_count"] > 0

    syntax_result = comfrey.syntax_detector.detect_parser_misalignment("def broken(", "code_generator")
    assert syntax_result.detected
    json_result = comfrey.syntax_detector.detect_parser_misalignment('{"ok": true}', "json_output")
    assert not json_result.detected

    format_result = comfrey.format_detector.detect_template_discrepancy(
        "Action: search\nThought: need data",
        "agent_step"
    )
    assert format_result.error_type.value == "format_template_discrepancy"

    class FakeRunnable:
        def invoke(self, input=None, config=None, **kwargs):
            return "Read docs. Read docs."

    wrapped_runnable = comfrey.instrument_langchain(FakeRunnable(), name="fake_runnable")
    assert wrapped_runnable.invoke("question") == "Read docs."

    try:
        from langchain_core.runnables import RunnableLambda
        langchain_runnable = RunnableLambda(lambda value: "Echo. Echo.")
        wrapped_langchain = comfrey.instrument_langchain(langchain_runnable, name="langchain_runnable")
        assert wrapped_langchain.invoke("question") == "Echo."
    except ImportError:
        pass

    paper_config = ComfreyConfig.create_paper_config()
    assert paper_config.embedding_provider == "openai_compatible"
    assert paper_config.embedding_model_name == "text-embedding-ada-002"
    assert paper_config.chat_provider == "openai_compatible"
    assert paper_config.strict_paper_mode
    assert not paper_config.allow_lightweight_fallbacks

    client_config = ComfreyConfig.create_paper_config()
    client_config.api_key = "Bearer test-token"
    client_config.api_base_url = "https://api.example.test/v1/chat/completions"
    client = OpenAICompatibleClient(client_config)
    assert client._required_api_key() == "test-token"
    assert (
        client._build_url("/v1/chat/completions")
        == "https://api.example.test/v1/chat/completions"
    )
    assert (
        client._build_url("/v1/embeddings")
        == "https://api.example.test/v1/embeddings"
    )
    client_config.api_base_url = "api.example.test/v1"
    assert (
        client._build_url("/v1/chat/completions")
        == "https://api.example.test/v1/chat/completions"
    )

    paper_config.api_base_url = ""
    paper_config.api_key = ""
    paper_config.api_base_url_file = None
    paper_config.api_key_file = None
    paper_config.api_base_url_env = "COMFREY_TEST_MISSING_BASE_URL"
    paper_config.api_key_env = "COMFREY_TEST_MISSING_API_KEY"
    try:
        EmbeddingProvider(paper_config).embed(["a", "b"])
    except RuntimeError as exc:
        assert "base URL is required" in str(exc)
    else:
        raise AssertionError("paper mode must fail fast when API config is missing")

    print("Comfrey smoke test passed")
    print(comfrey.get_statistics())


if __name__ == "__main__":
    main()
