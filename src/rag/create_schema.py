import weaviate
from weaviate.classes.config import Property, DataType, Configure

def create_schema(schema_name: str, mode = "full"):
    client = weaviate.connect_to_local(
        host = "weaviate",
        port = 8080,
        grpc_port=50051,
        skip_init_checks=True
    )
    try:
        if mode == "full":
            properties = [
                Property(name="article_id", data_type=DataType.TEXT),
                Property(name="mapc", data_type=DataType.TEXT),
                Property(name="article_name", data_type=DataType.TEXT),
                Property(name="note_content", data_type=DataType.TEXT),
                Property(name="content", data_type=DataType.TEXT),
                
            ]
        elif mode == "subject_name":
            properties = [
                Property(name="subject_name", data_type=DataType.TEXT),
                Property(name="subject_id", data_type=DataType.TEXT),
                Property(name="embedding_field", data_type=DataType.TEXT),
            ]
        elif mode == "closest_name":
            properties = [
                Property(name="subject_name", data_type=DataType.TEXT),
                Property(name="title_name", data_type=DataType.TEXT),
                Property(name="part_name", data_type=DataType.TEXT),
                Property(name="chapter_name", data_type=DataType.TEXT),
                Property(name="section_name", data_type=DataType.TEXT),
                Property(name="subsection_name", data_type=DataType.TEXT),
                Property(name="embedding_field", data_type=DataType.TEXT),
                Property(name="closest_id", data_type=DataType.TEXT),
            ]
        collection = client.collections.create(
            name=schema_name,
                properties=properties,
            # vector_config=Configure.Vectorizer.none(),  # Nếu bạn tự embedding
        )
        print(f"Schema '{schema_name}' created successfully.")
    finally:
        client.close()

if __name__ == "__main__":
    create_schema("bge_clean", mode="full")
