from bson import ObjectId
from datetime import datetime, date



def convert_mongo(item):
    if isinstance(item, list):
        return [convert_mongo(i) for i in item]
    if isinstance(item, dict):
        return {k: convert_mongo(v) for k, v in item.items()}
    if isinstance(item, ObjectId):
        return str(item)
    if isinstance(item, (datetime, date)):
        return item.isoformat() 
    return item