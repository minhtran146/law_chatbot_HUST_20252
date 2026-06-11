import uuid

generated_ids = set()

def generate_unique_id():
    while True:
        new_id = str(uuid.uuid4())
        if new_id not in generated_ids:
            generated_ids.add(new_id)
            return new_id
