import weaviate
import json
import os
os.environ['no_proxy'] = 'localhost,127.0.0.1'

client = weaviate.connect_to_local(
        host="weaviate",
        port=8080,
        grpc_port=50051,
        skip_init_checks=True,
    )


try:
    collection_name = "bge_clean"  # Thay đổi tên collection nếu cần
    subject_names_collection = client.collections.get(collection_name)

    # --- 1. HIỂN THỊ TỔNG SỐ LƯỢNG ---
    # Sử dụng Aggregate để đếm
    result = subject_names_collection.aggregate.over_all(total_count=True)
    print(f"=== TỔNG SỐ LƯỢNG TRONG COLLECTION '{collection_name}' ===")
    print(f"Total Count: {result.total_count}\n")

    # --- 2. HIỂN THỊ 1 SAMPLE ---
    # Lấy 1 đối tượng, bao gồm cả vector nếu muốn (include_vector=True)
    response = subject_names_collection.query.fetch_objects(limit=5, include_vector=False)

    if response.objects:
        sample = response.objects[1]
        print(f"=== 1 SAMPLE DATA FROM '{collection_name}' ===")
        print(f"ID: {sample.uuid}")
        print("Properties:")
        print(json.dumps(sample.properties, indent=4, ensure_ascii=False, default=str))
    else:
        print("Collection đang trống, không có mẫu nào để hiển thị.")

finally:
    client.close()