import weaviate

def delete_schema(schema_name: str):
    client = weaviate.connect_to_local(
        host = "127.0.0.1",
        port = 8080,
        skip_init_checks=True
    )
    try:
        client.collections.delete(schema_name)
        print(f"Schema '{schema_name}' deleted successfully.")
    finally:
        client.close()
if __name__ == "__main__":
    delete_schema("article_v6_qwen")