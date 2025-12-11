from bson import ObjectId


def convert_mongo(item):
    if isinstance(item, list):
        return [convert_mongo(i) for i in item]
    if isinstance(item, dict):
        return {k: convert_mongo(v) for k, v in item.items()}
    if isinstance(item, ObjectId):
        return str(item)
    return item