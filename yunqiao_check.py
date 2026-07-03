from src.config import ComfreyConfig
from src.embedding_provider import EmbeddingProvider
from src.openai_compatible_client import OpenAICompatibleClient


def main():
    config = ComfreyConfig.create_paper_config()
    embedding = EmbeddingProvider(config).embed(["Comfrey runtime check"])
    if not embedding or not embedding[0]:
        raise RuntimeError("Yunqiao embedding endpoint returned an empty vector")

    client = OpenAICompatibleClient(config)
    reply = client.chat_completion(
        "Return only the word ok.",
        "Say ok."
    )
    if not reply:
        raise RuntimeError("Yunqiao chat endpoint returned empty content")

    print("Yunqiao API check passed")
    print(f"embedding_dim={len(embedding[0])}")
    print(f"chat_reply={reply[:80]}")


if __name__ == "__main__":
    main()
