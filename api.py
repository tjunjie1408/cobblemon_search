import meilisearch
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from typing import Optional, List # 导入 List 和 Optional

# --- 配置 ---
MEILI_MASTER_KEY = '@Jason14' # !! 替换成你的密码 !!
MEILI_URL = 'http://127.0.0.1:7700'
INDEX_NAME = 'spawns'

# --- 连接 Meilisearch ---
try:
    client = meilisearch.Client(MEILI_URL, MEILI_MASTER_KEY)
    index = client.index(INDEX_NAME)
    stats = index.get_stats()
    print(f"--- 阶段三 (修改版) API ---")
    print(f"成功连接到 Meilisearch 索引 '{INDEX_NAME}'。")
    print(f"索引中共有 {stats.number_of_documents} 条扩充规则。")
except Exception as e:
    print(f"!! 严重错误：无法连接到 Meilisearch !!")
    print(f"错误: {e}")
    print("请确保 meilisearch.exe 正在运行，并且 MASTER_KEY 是正确的。")
    exit()

# --- 初始化 FastAPI 应用 ---
app = FastAPI(
    title="Cobblemon Spawn Search API",
    description="一个用于搜索宝可梦生成规则的 API"
)

# --- 允许跨域请求 (CORS) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # 允许所有来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- !! 升级版 API 端点 (Endpoint) !! ---
@app.get("/search")
async def search_spawns(
    # 搜索词 (q) 现在是可选的
    q: Optional[str] = Query(None, description="搜索查询词 (例如 'pikachu')"), 
    
    limit: int = Query(20, ge=1, le=100, description="返回结果的数量"),
    
    # --- 新增的过滤器 ---
    # 按属性筛选 (例如: type=type_grass)
    type: Optional[str] = Query(None, description="按属性筛选 (例如 'type_grass', 'type_fire')"),
    
    # 按稀有度筛选
    bucket: Optional[str] = Query(None, description="按稀有度筛选 (例如 'common', 'rare')"),
    
    # 按世代筛选
    gen: Optional[int] = Query(None, description="按世代筛选 (例如 1, 2, 9)")
):
    """
    在 Cobblemon 生成规则中进行高级搜索和筛选。
    """
    try:
        # 构建过滤器列表
        filter_list = []
        if type:
            # "features" 是一个数组，所以我们用 "IN" 来检查
            filter_list.append(f'features IN ["{type}"]') 
        if bucket:
            filter_list.append(f'bucket = "{bucket}"')
        if gen:
            # 'species.generation' 是一个数字
            filter_list.append(f'species.generation = {gen}') 

        # 将所有过滤器用 "AND" 组合起来
        filter_string = " AND ".join(filter_list)

        # 如果没有输入搜索词 (q)，则使用 '*' 进行“全匹配”搜索
        search_query = q if q else '*'

        search_options = {
            'limit': limit,
            'attributesToHighlight': ['species.name', 'pokemon'],
            'highlightPreTag': '<strong>',
            'highlightPostTag': '</strong>'
        }
        
        # 只有在有过滤器的情况下才添加 filter 字段
        if filter_string:
            search_options['filter'] = filter_string

        search_result = index.search(search_query, search_options)
        
        return search_result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"搜索时发生错误: {str(e)}")

# --- 启动服务器 ---
if __name__ == "__main__":
    print("启动 FastAPI 服务器，访问 http://127.0.0.1:8000")
    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=True)