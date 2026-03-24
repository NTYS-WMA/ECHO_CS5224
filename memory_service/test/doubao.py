import os
from volcenginesdkarkruntime import Ark
import time
# 初始化客户端
start = time.time()
client = Ark(
    # 从环境变量中读取您的方舟API Key
    # api_key=os.environ.get("ARK_API_KEY"),
    api_key="619ed7e4-b435-4ec9-93c0-c0a71a74d2d4",
    base_url="https://ark.cn-beijing.volces.com/api/v3"
)
response = client.embeddings.create(
    model="doubao-embedding-text-240715",
    input="Function Calling 是一种将大模型与外部工具和 API 相连的关键功能",
    encoding_format="float"
)
# 打印结果
print(f"向量维度: {len(response.data[0].embedding)}")
print(f"前10维向量: {response.data[0].embedding[:10]}")
print(time.time()-start)