import os
import json
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from typing import Optional, List
from sqlalchemy import create_engine, text, sql
from sqlalchemy.orm import sessionmaker

# --- 1. 配置 ---
print("--- 阶段三 (Postgres版) API ---")

# 从 Render 环境变量中读取数据库 URL
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    print("!! 严重错误: 未能在环境变量中找到 'DATABASE_URL' !!")
    # 这是一个备用方案，用于你万一想在本地运行 api.py
    # 你需要在这里粘贴 Render 提供的 "External Connection URL"
    # DATABASE_URL = "postgres://user:password@host:port/database" 
    if "YOUR_EXTERNAL_URL" in DATABASE_URL: # 检查是否是占位符
        print("请在 api.py 中设置你的 'External Connection URL' 以便在本地测试。")
        exit()

# 确保 URL 格式正确
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

try:
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    print(f"成功创建数据库连接池。")
except Exception as e:
    print(f"!! 严重错误：无法创建数据库引擎 !!")
    print(f"错误: {e}")
    exit()

# --- 2. 初始化 FastAPI 应用 ---
app = FastAPI(
    title="Cobblemon Spawn Search API (Postgres Edition)",
    description="一个用于搜索宝可梦生成规则的 API"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# --- 3. 升级版 API 端点 (Endpoint) ---
@app.get("/search")
async def search_spawns(
    q: Optional[str] = Query(None, description="搜索查询词 (例如 'pikachu')"), 
    limit: int = Query(20, ge=1, le=100, description="返回结果的数量"),
    type: Optional[str] = Query(None, description="按属性筛选 (例如 'type_grass', 'type_fire')"),
    bucket: Optional[str] = Query(None, description="按稀有度筛选 (例如 'common', 'rare')"),
    gen: Optional[int] = Query(None, description="按世代筛选 (例如 1, 2, 9)")
):
    """
    在 Cobblemon 生成规则中进行高级 SQL 搜索和筛选。
    """
    try:
        with SessionLocal() as session:
            # 基础查询：我们只选择 'data' 列，因为它包含完整的 JSON
            query = "SELECT data FROM spawns WHERE 1=1"
            params = {} # 用于安全地传递参数

            if q:
                # ILIKE 用于不区分大小写的搜索
                # 'q' 必须在两边加上 % 才能进行模糊匹配
                query += " AND pokemon_name ILIKE :q"
                params['q'] = f"%{q.lower()}%"
            
            if type:
                # 'features' 是一个数组，我们使用 @> (contains) 或 = ANY (equals any)
                query += " AND :type = ANY(features)"
                params['type'] = type
            
            if bucket:
                query += " AND bucket = :bucket"
                params['bucket'] = bucket
            
            if gen:
                query += " AND generation = :gen"
                params['gen'] = gen
            
            # 添加排序和限制
            query += " ORDER BY level_min DESC, pokemon_name ASC"
            query += " LIMIT :limit"
            params['limit'] = limit

            # 执行查询
            sql_query = text(query)
            result = session.execute(sql_query, params)
            
            # 将结果 (只包含 'data' 列) 转换为 Meilisearch 风格的 'hits' 列表
            hits = [row[0] for row in result] 
            
            # 模拟 Meilisearch 的返回结构
            return {
                "hits": hits,
                "query": q,
                "processingTimeMs": 100, # 这是一个模拟值
                "limit": limit,
                "nbHits": len(hits) # 注意：这不是总命中数，只是当前批次的
            }
            
    except Exception as e:
        print(f"查询时发生错误: {e}") # 在服务器日志中打印错误
        raise HTTPException(status_code=500, detail=f"搜索时发生错误: {str(e)}")

# --- 4. 启动服务器 ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000)) # Render 会提供 $PORT 环境变量
    print(f"启动 FastAPI 服务器，在端口 {port} 上...")
    # 监听 0.0.0.0 才能让 Render 访问

    uvicorn.run("api:app", host="0.0.0.0", port=port)
